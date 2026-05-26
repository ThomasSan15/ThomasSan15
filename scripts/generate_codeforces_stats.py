#!/usr/bin/env python3
"""
Codeforces Stats SVG Card Generator
Generates two premium SVG cards:
  - generated/codeforces_overview.svg
  - generated/codeforces_tags.svg

Usage:
  python scripts/generate_codeforces_stats.py --user ThomasBA --out generated

No API key required — Codeforces public API only.
"""

import os
import json
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── CF API ───────────────────────────────────────────────────────────────────

CF_BASE = "https://codeforces.com/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

RANK_ORDER = [
    "newbie", "pupil", "specialist", "expert",
    "candidate master", "master", "international master",
    "grandmaster", "international grandmaster", "legendary grandmaster",
]

RANK_COLORS = {
    "newbie":                   "#808080",
    "pupil":                    "#008000",
    "specialist":               "#03a89e",
    "expert":                   "#4f8cff",
    "candidate master":         "#aa00aa",
    "master":                   "#ff8c00",
    "international master":     "#ff8c00",
    "grandmaster":              "#ff3030",
    "international grandmaster":"#ff3030",
    "legendary grandmaster":    "#ff3030",
}

TRACKED_TAGS = [
    "dp",
    "graphs",
    "greedy",
    "math",
    "binary search",
    "data structures",
    "implementation",
    "strings",
    "constructive algorithms",
    "brute force",
]


def cf_get(method: str, params: dict, retries: int = 3) -> dict:
    url = f"{CF_BASE}/{method}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "OK":
                return data["result"]
            raise RuntimeError(f"CF API error: {data.get('comment', 'unknown')}")
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_user_info(handle: str) -> dict:
    result = cf_get("user.info", {"handles": handle})
    return result[0]


def fetch_user_rating(handle: str) -> list:
    """Returns list of rating change objects (contest history)."""
    try:
        return cf_get("user.rating", {"handle": handle})
    except Exception:
        return []


def fetch_user_submissions(handle: str) -> list:
    """
    Fetch ALL submissions using pagination.
    """

    all_submissions = []
    start = 1
    batch_size = 10000

    while True:
        batch = cf_get(
            "user.status",
            {
                "handle": handle,
                "from": start,
                "count": batch_size,
            }
        )

        if not batch:
            break

        all_submissions.extend(batch)

        print(f"      fetched {len(all_submissions)} submissions...")

        if len(batch) < batch_size:
            break

        start += batch_size

        time.sleep(0.2)

    return all_submissions


def compute_streak(submissions: list) -> int:
    """
    Current streak of consecutive days with at least one accepted submission.
    """

    ac_days = set()

    for sub in submissions:
        if sub.get("verdict") == "OK":
            ts = sub.get("creationTimeSeconds", 0)
            day = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            ac_days.add(day)

    if not ac_days:
        return 0

    today = datetime.now(timezone.utc).date()

    # If today has no AC, allow streak to start yesterday
    current = today if today in ac_days else today - timedelta(days=1)

    streak = 0

    while current in ac_days:
        streak += 1
        current -= timedelta(days=1)

    return streak


def compute_unique_solved(submissions: list) -> dict:
    """
    Single source of truth: build the deduplicated set of solved problems.

    Returns a dict:
      {
        "total":  int,                              # unique solved count
        "tags":   { tag_name: count, ... },         # per-tag unique solved count
        "solved_keys": set of (contestId, index),   # for any further use
      }

    Rules:
      - Only verdict == "OK" submissions count.
      - A (contestId, index) pair is counted AT MOST ONCE globally.
        If the same problem appears multiple times, only the FIRST accepted
        submission is used (order from the API, newest-first, so we iterate
        reversed to keep the earliest).
      - Tag frequencies are derived from those unique problems only.
      - Percentages must be computed as  count / total_unique_solved * 100.
    """
    # API returns submissions newest-first; reverse so earliest AC wins the slot.
    solved_problems: dict[tuple, set] = {}
    for sub in reversed(submissions):
        if sub.get("verdict") != "OK":
            continue
        prob = sub.get("problem", {})
        key  = (prob.get("contestId", 0), prob.get("index", ""))
        # Only register each problem once (first/earliest accepted submission)
        if key not in solved_problems:
            solved_problems[key] = set(prob.get("tags", []))

    tag_counts: dict[str, int] = defaultdict(int)
    for tags in solved_problems.values():
        for tag in tags:
            tag_counts[tag] += 1

    return {
        "total":       len(solved_problems),
        "tags":        dict(tag_counts),
        "solved_keys": set(solved_problems.keys()),
    }


# Keep a thin wrapper so the rest of the code calling compute_solved_total still works
def compute_solved_total(submissions: list) -> int:
    return compute_unique_solved(submissions)["total"]


def compute_tag_stats(submissions: list) -> dict:
    """Kept for backward compatibility — delegates to compute_unique_solved."""
    return compute_unique_solved(submissions)["tags"]


# ── SVG HELPERS ──────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def rating_to_rank(rating: int) -> str:
    if rating < 1200: return "newbie"
    if rating < 1400: return "pupil"
    if rating < 1600: return "specialist"
    if rating < 1900: return "expert"
    if rating < 2100: return "candidate master"
    if rating < 2300: return "master"
    if rating < 2400: return "international master"
    if rating < 2600: return "grandmaster"
    if rating < 3000: return "international grandmaster"
    return "legendary grandmaster"


def rating_to_max_for_rank(rank: str) -> int:
    """Upper bound of each rank (for progress ring calculation)."""
    bounds = {
        "newbie": 1200, "pupil": 1400, "specialist": 1600,
        "expert": 1900, "candidate master": 2100, "master": 2300,
        "international master": 2400, "grandmaster": 2600,
        "international grandmaster": 3000, "legendary grandmaster": 4000,
    }
    return bounds.get(rank, 4000)


def rating_floor(rank: str) -> int:
    floors = {
        "newbie": 0, "pupil": 1200, "specialist": 1400,
        "expert": 1600, "candidate master": 1900, "master": 2100,
        "international master": 2300, "grandmaster": 2400,
        "international grandmaster": 2600, "legendary grandmaster": 3000,
    }
    return floors.get(rank, 0)


def arc_path(cx, cy, r, start_deg, end_deg):
    """SVG arc path for a donut segment."""
    import math
    def pt(deg):
        rad = math.radians(deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    large = 1 if (end_deg - start_deg) > 180 else 0
    sx, sy = pt(start_deg)
    ex, ey = pt(end_deg)
    return f"M {sx:.2f} {sy:.2f} A {r} {r} 0 {large} 1 {ex:.2f} {ey:.2f}"


def circumference(r):
    import math
    return 2 * math.pi * r


# ── CARD 1: OVERVIEW ─────────────────────────────────────────────────────────

def make_overview_svg(user: dict, submissions: list, contests: list, total_solved: int) -> str:
    handle        = user.get("handle", "")
    rating        = user.get("rating", 0)
    max_rating    = user.get("maxRating", 0)
    rank          = (user.get("rank", "newbie") or "newbie").lower()
    max_rank      = (user.get("maxRank", "newbie") or "newbie").lower()
    last_online   = datetime.fromtimestamp(
        user.get("lastOnlineTimeSeconds", 0), tz=timezone.utc
    ).strftime("%Y-%m-%d")
    streak        = compute_streak(submissions)
    total_contests = len(contests)
    generated     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rank_color    = RANK_COLORS.get(rank, "#4f8cff")
    max_rank_color= RANK_COLORS.get(max_rank, "#4f8cff")

    # Rating ring: progress within current rank bracket
    ring_r        = 44
    ring_cx       = 64
    ring_cy       = 100
    rank_floor    = rating_floor(rank)
    rank_ceil     = rating_to_max_for_rank(rank)
    ring_pct      = clamp((rating - rank_floor) / max(rank_ceil - rank_floor, 1), 0, 1)
    circ          = circumference(ring_r)
    dash_filled   = ring_pct * circ
    dash_gap      = circ - dash_filled

    W, H = 420, 200

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Codeforces Stats – {handle}">
  <title>Codeforces Stats – {handle}</title>
  <defs>
    <!-- Background -->
    <linearGradient id="cf-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <!-- Ring track glow -->
    <filter id="cf-glow">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Subtle inner shadow -->
    <filter id="cf-inner">
      <feGaussianBlur stdDeviation="1" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="cf-clip"><rect width="{W}" height="{H}" rx="12"/></clipPath>
  </defs>

  <!-- Card -->
  <rect width="{W}" height="{H}" rx="12" fill="url(#cf-bg)" clip-path="url(#cf-clip)"/>
  <!-- Top accent -->
  <rect width="{W}" height="2" fill="{rank_color}" opacity="0.8"/>
  <!-- Left border -->
  <rect width="3" height="{H}" fill="{rank_color}"/>

  <!-- Header -->
  <text x="20" y="22" font-family="JetBrains Mono,monospace" font-size="10"
        fill="{rank_color}" font-weight="700" letter-spacing="2">CODEFORCES</text>
  <text x="20" y="40" font-family="JetBrains Mono,monospace" font-size="17"
        fill="#e6edf3" font-weight="700">{handle}</text>
  <text x="{W-14}" y="22" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="end">{generated}</text>

  <!-- Divider -->
  <line x1="20" y1="50" x2="{W-14}" y2="50" stroke="#1c2128" stroke-width="1"/>

  <!-- ── Rating ring (left) ── -->
  <!-- Track -->
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}" fill="none"
          stroke="#1c2128" stroke-width="7"/>
  <!-- Arc bg glow -->
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}" fill="none"
          stroke="{rank_color}" stroke-width="7" opacity="0.08"/>
  <!-- Animated filled arc -->
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}" fill="none"
          stroke="{rank_color}" stroke-width="7"
          stroke-dasharray="{dash_filled:.2f} {dash_gap:.2f}"
          stroke-linecap="round"
          transform="rotate(-90 {ring_cx} {ring_cy})"
          filter="url(#cf-glow)">
    <animate attributeName="stroke-dasharray"
             from="0 {circ:.2f}"
             to="{dash_filled:.2f} {dash_gap:.2f}"
             dur="1.4s" fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </circle>
  <!-- Rating number inside ring -->
  <text x="{ring_cx}" y="{ring_cy - 8}" font-family="JetBrains Mono,monospace"
        font-size="18" fill="#e6edf3" font-weight="700" text-anchor="middle">{rating}</text>
  <text x="{ring_cx}" y="{ring_cy + 8}" font-family="JetBrains Mono,monospace"
        font-size="9" fill="{rank_color}" text-anchor="middle" letter-spacing="1">RATING</text>
  <text x="{ring_cx}" y="{ring_cy + 22}" font-family="JetBrains Mono,monospace"
        font-size="8" fill="#484f58" text-anchor="middle">max {max_rating}</text>

  <!-- ── Stats grid (right of ring) ── -->
  <!-- Row 1 -->
  <text x="138" y="72" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">RANK</text>
  <text x="260" y="72" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">MAX RANK</text>
  <text x="138" y="88" font-family="JetBrains Mono,monospace" font-size="13"
        fill="{rank_color}" font-weight="700">{rank.title()}</text>
  <text x="260" y="88" font-family="JetBrains Mono,monospace" font-size="13"
        fill="{max_rank_color}" font-weight="700">{max_rank.title()}</text>

  <!-- Row 2 -->
  <text x="138" y="112" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">SOLVED</text>
  <text x="260" y="112" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">CONTESTS</text>
  <text x="138" y="128" font-family="JetBrains Mono,monospace" font-size="20"
        fill="#e6edf3" font-weight="700">{total_solved}</text>
  <text x="260" y="128" font-family="JetBrains Mono,monospace" font-size="20"
        fill="#e6edf3" font-weight="700">{total_contests}</text>

  <!-- Row 3 -->
  <text x="138" y="152" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">STREAK</text>
  <text x="260" y="152" font-family="JetBrains Mono,monospace" font-size="9"
        fill="#8b949e" letter-spacing="1">LAST ACTIVE</text>
  <text x="138" y="168" font-family="JetBrains Mono,monospace" font-size="17"
        fill="#e6edf3" font-weight="700">{streak}<tspan font-size="10" fill="#8b949e"> days</tspan></text>
  <text x="260" y="168" font-family="JetBrains Mono,monospace" font-size="13"
        fill="#c9d1d9">{last_online}</text>

  <!-- Bottom progress bar: solved / 1000 benchmark -->
  <line x1="20" y1="180" x2="{W-14}" y2="180" stroke="#1c2128" stroke-width="1"/>
  <text x="20"  y="194" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58">solved progress</text>
  <rect x="110" y="187" width="{W-124}" height="5" rx="2" fill="#1c2128"/>
  <rect x="110" y="187" width="{clamp(int(total_solved / 500 * (W-124)), 0, W-124)}" height="5" rx="2"
        fill="{rank_color}" opacity="0.7">
    <animate attributeName="width" from="0"
             to="{clamp(int(total_solved / 500 * (W-124)), 0, W-124)}"
             dur="1.2s" fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{W-14}" y="194" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="end">{total_solved}/500</text>

  <!-- Border -->
  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#21262d" stroke-width="1"/>
</svg>"""


# ── CARD 2: TAG PROGRESS ─────────────────────────────────────────────────────

def make_tags_svg(tag_counts: dict, user: dict, total_solved: int) -> str:
    """
    tag_counts    — { tag: unique_solved_count }  (from compute_unique_solved)
    total_solved  — total unique solved problems across ALL tags/categories
                    used as the denominator for percentages so that
                    pct = tag_count / total_solved * 100  (not relative to max tag)
    """
    handle    = user.get("handle", "")
    accent    = "#4f8cff"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build display rows sorted by solved count desc
    rows = [(tag, tag_counts.get(tag, 0)) for tag in TRACKED_TAGS]
    rows.sort(key=lambda x: -x[1])

    # Bar width is relative to the top tag so bars fill the card nicely.
    # Percentage label is always count / total_solved (correct semantics).
    max_count   = max((r[1] for r in rows), default=1) or 1
    denom_pct   = max(total_solved, 1)   # denominator for percentage labels

    TAG_LABELS = {
        "dp":                      "Dynamic Programming",
        "graphs":                  "Graphs",
        "greedy":                  "Greedy",
        "math":                    "Math",
        "binary search":           "Binary Search",
        "data structures":         "Data Structures",
        "implementation":          "Implementation",
        "strings":                 "Strings",
        "constructive algorithms": "Constructive",
        "brute force":             "Brute Force",
    }

    row_h    = 30
    pad      = 16
    bar_max  = 220
    header_h = 48
    height   = pad * 2 + header_h + len(rows) * row_h
    W        = 420

    rows_svg = ""
    for i, (tag, count) in enumerate(rows):
        # Bar width: relative to the largest tag (visual scaling)
        bw         = clamp(int((count / max_count) * bar_max), 0, bar_max)
        # Percentage: count / total unique solved problems (semantic meaning)
        pct_val    = count / denom_pct * 100
        pct        = f"{pct_val:.0f}%"
        y          = pad + header_h + i * row_h
        dur        = f"{1.0 + i * 0.07:.2f}s"
        label      = TAG_LABELS.get(tag, tag.title())
        bar_color  = accent if count == max_count else "#2d4a7a"
        text_color = accent if count == max_count else "#8b949e"

        rows_svg += f"""
  <text x="16" y="{y+16}" font-family="JetBrains Mono,monospace" font-size="11"
        fill="#c9d1d9">{label}</text>
  <rect x="152" y="{y+7}" width="{bar_max}" height="10" rx="5" fill="#161b22"/>
  <rect x="152" y="{y+7}" width="{bw}" height="10" rx="5"
        fill="{bar_color}" opacity="0.9">
    <animate attributeName="width" from="0" to="{bw}" dur="{dur}"
             fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{152+bar_max+8}" y="{y+16}" font-family="JetBrains Mono,monospace"
        font-size="10" fill="{text_color}">{count}</text>
  <text x="{152+bar_max+38}" y="{y+16}" font-family="JetBrains Mono,monospace"
        font-size="9" fill="#484f58" text-anchor="end">{pct}</text>"""

    return f"""<svg width="{W}" height="{height}" viewBox="0 0 {W} {height}"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Codeforces Tag Progress – {handle}">
  <title>Codeforces Tag Progress – {handle}</title>
  <defs>
    <linearGradient id="cf2-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <clipPath id="cf2-clip"><rect width="{W}" height="{height}" rx="12"/></clipPath>
  </defs>
  <rect width="{W}" height="{height}" rx="12" fill="url(#cf2-bg)" clip-path="url(#cf2-clip)"/>
  <rect width="3" height="{height}" fill="{accent}"/>
  <rect width="{W}" height="2" fill="{accent}" opacity="0.8"/>

  <text x="16" y="20" font-family="JetBrains Mono,monospace" font-size="10"
        fill="{accent}" font-weight="700" letter-spacing="2">PROBLEM TAGS</text>
  <text x="16" y="36" font-family="JetBrains Mono,monospace" font-size="13"
        fill="#e6edf3" font-weight="700">{handle}</text>
  <text x="{W-14}" y="20" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="end">{generated}</text>
  <line x1="16" y1="{pad+header_h-4}" x2="{W-14}" y2="{pad+header_h-4}"
        stroke="#1c2128" stroke-width="1"/>

  {rows_svg}

  <rect width="{W}" height="{height}" rx="12" fill="none" stroke="#21262d" stroke-width="1"/>
</svg>"""


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Codeforces SVG cards")
    parser.add_argument("--user", required=True, help="Codeforces handle")
    parser.add_argument("--out",  default="generated")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"[1/4] Fetching user info for {args.user}...")
    user = fetch_user_info(args.user)
    print(f"      rating={user.get('rating', 'N/A')}  rank={user.get('rank', 'N/A')}")

    print("[2/4] Fetching contest history...")
    contests = fetch_user_rating(args.user)
    print(f"      contests={len(contests)}")

    print("[3/4] Fetching submissions (may take a moment)...")
    submissions  = fetch_user_submissions(args.user)
    solved_stats = compute_unique_solved(submissions)
    total_solved = solved_stats["total"]
    tag_counts   = solved_stats["tags"]

    print(f"      raw submissions : {len(submissions)}")
    print(f"      unique solved   : {total_solved}")
    print(f"      tag breakdown   : { {t: tag_counts.get(t,0) for t in TRACKED_TAGS} }")

    print("[4/4] Generating SVGs...")

    overview_path = os.path.join(args.out, "codeforces_overview.svg")
    with open(overview_path, "w", encoding="utf-8") as f:
        # Pass the already-computed total so make_overview_svg doesn't re-scan
        f.write(make_overview_svg(user, submissions, contests, total_solved))
    print(f"      ✓ {overview_path}")

    tags_path = os.path.join(args.out, "codeforces_tags.svg")
    with open(tags_path, "w", encoding="utf-8") as f:
        f.write(make_tags_svg(tag_counts, user, total_solved))
    print(f"      ✓ {tags_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
