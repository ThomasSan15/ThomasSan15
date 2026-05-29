#!/usr/bin/env python3
"""
Codeforces Stats SVG Card Generator
Generates:
  - generated/codeforces_overview.svg
  - generated/codeforces_tags.svg

Usage:
  python scripts/generate_codeforces_stats.py --user ThomasBA --out generated
"""

import os
import math
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── CONSTANTS ────────────────────────────────────────────────────────────────

CF_BASE = "https://codeforces.com/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Codeforces uses Moscow time (UTC+3) for its activity calendar / streak display.
# Using any other timezone will shift day boundaries and break streak counts.
MOSCOW_TZ = timezone(timedelta(hours=3))

RANK_COLORS = {
    "newbie":                    "#808080",
    "pupil":                     "#008000",
    "specialist":                "#03a89e",
    "expert":                    "#4f8cff",
    "candidate master":          "#aa00aa",
    "master":                    "#ff8c00",
    "international master":      "#ff8c00",
    "grandmaster":               "#ff3030",
    "international grandmaster": "#ff3030",
    "legendary grandmaster":     "#ff3030",
}

TRACKED_TAGS = [
    "math",
    "implementation",
    "greedy",
    "strings",
    "brute force",
    "constructive algorithms",
    "dp",
    "binary search",
    "graphs",
    "data structures",
]

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

# ── CF API ────────────────────────────────────────────────────────────────────

def cf_get(method: str, params: dict, retries: int = 3) -> list:
    url = f"{CF_BASE}/{method}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "OK":
                return data["result"]
            raise RuntimeError(f"CF API: {data.get('comment', 'unknown error')}")
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_user_info(handle: str) -> dict:
    return cf_get("user.info", {"handles": handle})[0]


def fetch_user_rating(handle: str) -> list:
    try:
        return cf_get("user.rating", {"handle": handle})
    except Exception:
        return []


def fetch_user_submissions(handle: str) -> list:
    """Fetch ALL submissions with pagination (handles > 10 000 subs)."""
    all_subs   = []
    start      = 1
    batch_size = 10_000

    while True:
        batch = cf_get("user.status", {
            "handle": handle,
            "from":   start,
            "count":  batch_size,
        })
        if not batch:
            break
        all_subs.extend(batch)
        print(f"      fetched {len(all_subs)} submissions so far...")
        if len(batch) < batch_size:
            break
        start += batch_size
        time.sleep(0.3)

    return all_subs


# ── STATS ENGINE ─────────────────────────────────────────────────────────────

def build_stats(submissions: list) -> dict:
    """
    Single-pass computation of all stats from the submissions list.

    Deduplication key
    -----------------
    Codeforces identifies a problem as (contestId, index).
    - `problemsetName` is NOT used — it can be None or "" for the same problem
      depending on how it was submitted, which causes double-counting.
    - `name` is NOT used — same problem can appear in mirror contests.
    - contestId is normalised: None → 0 (some problemset submissions omit it).
    - This exactly matches what the CF website counts as "solved problems".

    Streak timezone
    ---------------
    Codeforces activity calendar and streak display use Moscow time (UTC+3).
    Using any other timezone shifts day boundaries and produces wrong streaks.
    We use Moscow time for both ac_days collection AND "today" computation.

    Returns
    -------
    {
        "total_solved"   : int,
        "tags"           : { tag: count },
        "current_streak" : int,   # consecutive days up to today (or yesterday)
        "max_streak"     : int,   # all-time best
    }
    """
    # ── pass 1: deduplicate AC submissions ───────────────────────────────────
    # API returns newest-first. Reverse so the EARLIEST AC wins the slot
    # (consistent with CF's "first accepted" display).
    solved: dict = {}           # (contestId_int, index_str) -> [tags]
    ac_days: set = set()        # dates in Moscow timezone

    for sub in reversed(submissions):
        if sub.get("verdict") != "OK":
            continue

        prob = sub.get("problem", {})

        # Normalised key — matches CF website logic exactly
        contest_id = prob.get("contestId") or 0          # None → 0
        index      = (prob.get("index") or "").upper()   # normalise "a" → "A"
        key        = (int(contest_id), index)

        if key not in solved:
            solved[key] = list(prob.get("tags", []))

        # Collect the submission day in Moscow time
        ts  = sub.get("creationTimeSeconds", 0)
        day = datetime.fromtimestamp(ts, tz=MOSCOW_TZ).date()
        ac_days.add(day)

    # ── pass 2: tag counts (from unique solved problems only) ─────────────────
    tag_counts: dict = defaultdict(int)
    for tags in solved.values():
        for tag in tags:
            tag_counts[tag] += 1

    # ── pass 3: streak (Moscow timezone, timedelta arithmetic) ────────────────
    today     = datetime.now(MOSCOW_TZ).date()
    yesterday = today - timedelta(days=1)

    # Allow yesterday as streak start if no submission yet today
    start = today if today in ac_days else yesterday

    current_streak = 0
    d = start
    while d in ac_days:
        current_streak += 1
        d -= timedelta(days=1)

    # All-time max streak
    max_streak = 0
    running    = 0
    prev       = None
    for day in sorted(ac_days):
        if prev is not None and (day - prev) == timedelta(days=1):
            running += 1
        else:
            running = 1
        if running > max_streak:
            max_streak = running
        prev = day

    return {
        "total_solved":    len(solved),
        "tags":            dict(tag_counts),
        "current_streak":  current_streak,
        "max_streak":      max_streak,
    }


# ── SVG HELPERS ───────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def circumference(r: float) -> float:
    return 2 * math.pi * r


def rank_floor(rank: str) -> int:
    return {
        "newbie": 0, "pupil": 1200, "specialist": 1400,
        "expert": 1600, "candidate master": 1900, "master": 2100,
        "international master": 2300, "grandmaster": 2400,
        "international grandmaster": 2600, "legendary grandmaster": 3000,
    }.get(rank, 0)


def rank_ceil(rank: str) -> int:
    return {
        "newbie": 1200, "pupil": 1400, "specialist": 1600,
        "expert": 1900, "candidate master": 2100, "master": 2300,
        "international master": 2400, "grandmaster": 2600,
        "international grandmaster": 3000, "legendary grandmaster": 4000,
    }.get(rank, 4000)


# ── CARD 1: OVERVIEW ──────────────────────────────────────────────────────────

def make_overview_svg(user: dict, stats: dict, contests: list) -> str:
    handle         = user.get("handle", "")
    rating         = user.get("rating") or 0
    max_rating     = user.get("maxRating") or 0
    rank           = (user.get("rank") or "newbie").lower()
    max_rank       = (user.get("maxRank") or "newbie").lower()
    last_online    = datetime.fromtimestamp(
        user.get("lastOnlineTimeSeconds", 0), tz=timezone.utc
    ).strftime("%Y-%m-%d")
    total_solved   = stats["total_solved"]
    streak         = stats["current_streak"]
    total_contests = len(contests)
    generated      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rank_color     = RANK_COLORS.get(rank, "#4f8cff")
    max_rank_color = RANK_COLORS.get(max_rank, "#4f8cff")

    # Rating ring
    ring_r     = 44
    ring_cx    = 64
    ring_cy    = 100
    rf         = rank_floor(rank)
    rc         = rank_ceil(rank)
    ring_pct   = clamp((rating - rf) / max(rc - rf, 1), 0, 1)
    circ       = circumference(ring_r)
    dash_on    = ring_pct * circ
    dash_off   = circ - dash_on

    # Bottom bar: scale to nearest 500 above current solved
    bar_target = max(500, ((total_solved // 500) + 1) * 500)
    bar_w_max  = 286   # W - 124
    bar_w      = clamp(int(total_solved / bar_target * bar_w_max), 0, bar_w_max)

    W, H = 420, 200

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Codeforces Stats – {handle}">
  <title>Codeforces Stats – {handle}</title>
  <defs>
    <linearGradient id="cf-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <filter id="cf-glow">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="cf-clip"><rect width="{W}" height="{H}" rx="12"/></clipPath>
  </defs>

  <rect width="{W}" height="{H}" rx="12" fill="url(#cf-bg)" clip-path="url(#cf-clip)"/>
  <rect width="{W}" height="2" fill="{rank_color}" opacity="0.8"/>
  <rect width="3" height="{H}" fill="{rank_color}"/>

  <text x="20" y="22" font-family="JetBrains Mono,monospace" font-size="10"
        fill="{rank_color}" font-weight="700" letter-spacing="2">CODEFORCES</text>
  <text x="20" y="40" font-family="JetBrains Mono,monospace" font-size="17"
        fill="#e6edf3" font-weight="700">{handle}</text>
  <text x="{W-14}" y="22" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="end">{generated}</text>
  <line x1="20" y1="50" x2="{W-14}" y2="50" stroke="#1c2128" stroke-width="1"/>

  <!-- Rating ring -->
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}"
          fill="none" stroke="#1c2128" stroke-width="7"/>
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}"
          fill="none" stroke="{rank_color}" stroke-width="7" opacity="0.08"/>
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}"
          fill="none" stroke="{rank_color}" stroke-width="7"
          stroke-dasharray="{dash_on:.2f} {dash_off:.2f}"
          stroke-linecap="round"
          transform="rotate(-90 {ring_cx} {ring_cy})"
          filter="url(#cf-glow)">
    <animate attributeName="stroke-dasharray"
             from="0 {circ:.2f}" to="{dash_on:.2f} {dash_off:.2f}"
             dur="1.4s" fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </circle>
  <text x="{ring_cx}" y="{ring_cy - 8}"
        font-family="JetBrains Mono,monospace" font-size="18"
        fill="#e6edf3" font-weight="700" text-anchor="middle">{rating or "—"}</text>
  <text x="{ring_cx}" y="{ring_cy + 8}"
        font-family="JetBrains Mono,monospace" font-size="9"
        fill="{rank_color}" text-anchor="middle" letter-spacing="1">RATING</text>
  <text x="{ring_cx}" y="{ring_cy + 22}"
        font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="middle">max {max_rating or "—"}</text>

  <!-- Stats grid -->
  <text x="138" y="72"  font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">RANK</text>
  <text x="280" y="72"  font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">MAX RANK</text>
  <text x="138" y="88"  font-family="JetBrains Mono,monospace" font-size="13" fill="{rank_color}" font-weight="700">{rank.title()}</text>
  <text x="280" y="88"  font-family="JetBrains Mono,monospace" font-size="13" fill="{max_rank_color}" font-weight="700">{max_rank.title()}</text>

  <text x="138" y="112" font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">SOLVED</text>
  <text x="280" y="112" font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">CONTESTS</text>
  <text x="138" y="128" font-family="JetBrains Mono,monospace" font-size="20" fill="#e6edf3" font-weight="700">{total_solved}</text>
  <text x="280" y="128" font-family="JetBrains Mono,monospace" font-size="20" fill="#e6edf3" font-weight="700">{total_contests}</text>

  <text x="138" y="152" font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">STREAK</text>
  <text x="280" y="152" font-family="JetBrains Mono,monospace" font-size="9" fill="#8b949e" letter-spacing="1">LAST ACTIVE</text>
  <text x="138" y="168" font-family="JetBrains Mono,monospace" font-size="17" fill="#e6edf3" font-weight="700">{streak}<tspan font-size="10" fill="#8b949e"> days</tspan></text>
  <text x="280" y="168" font-family="JetBrains Mono,monospace" font-size="13" fill="#c9d1d9">{last_online}</text>

  <!-- Bottom progress bar -->
  <line x1="20" y1="180" x2="{W-14}" y2="180" stroke="#1c2128" stroke-width="1"/>
  <text x="20" y="194" font-family="JetBrains Mono,monospace" font-size="8" fill="#484f58">solved progress</text>
  <rect x="110" y="187" width="{bar_w_max}" height="5" rx="2" fill="#1c2128"/>
  <rect x="110" y="187" width="{bar_w}" height="5" rx="2" fill="{rank_color}" opacity="0.7">
    <animate attributeName="width" from="0" to="{bar_w}"
             dur="1.2s" fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{W-14}" y="194" font-family="JetBrains Mono,monospace" font-size="8"
        fill="#484f58" text-anchor="end">{total_solved}/{bar_target}</text>

  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#21262d" stroke-width="1"/>
</svg>"""


# ── CARD 2: TAG PROGRESS ──────────────────────────────────────────────────────

def make_tags_svg(stats: dict, user: dict) -> str:
    handle       = user.get("handle", "")
    accent       = "#4f8cff"
    generated    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tag_counts   = stats["tags"]
    total_solved = stats["total_solved"]
    denom        = max(total_solved, 1)

    rows = sorted(
        [(tag, tag_counts.get(tag, 0)) for tag in TRACKED_TAGS],
        key=lambda x: -x[1]
    )

    # Bar width scales to the top tag (visual); percentage uses total solved (semantic)
    max_count = max((r[1] for r in rows), default=1) or 1

    row_h    = 30
    pad      = 16
    bar_max  = 220
    header_h = 48
    W        = 420
    height   = pad * 2 + header_h + len(rows) * row_h

    rows_svg = ""
    for i, (tag, count) in enumerate(rows):
        bw         = clamp(int(count / max_count * bar_max), 0, bar_max)
        pct        = f"{count / denom * 100:.0f}%"
        y          = pad + header_h + i * row_h
        dur        = f"{1.0 + i * 0.07:.2f}s"
        label      = TAG_LABELS.get(tag, tag.title())
        bar_color  = accent if count == max_count else "#2d4a7a"
        text_color = accent if count == max_count else "#8b949e"

        rows_svg += f"""
  <text x="16" y="{y+16}" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9d1d9">{label}</text>
  <rect x="152" y="{y+7}" width="{bar_max}" height="10" rx="5" fill="#161b22"/>
  <rect x="152" y="{y+7}" width="{bw}" height="10" rx="5" fill="{bar_color}" opacity="0.9">
    <animate attributeName="width" from="0" to="{bw}" dur="{dur}"
             fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{152+bar_max+8}" y="{y+16}" font-family="JetBrains Mono,monospace" font-size="10" fill="{text_color}">{count}</text>
  <text x="{152+bar_max+40}" y="{y+16}" font-family="JetBrains Mono,monospace" font-size="9" fill="#484f58" text-anchor="end">{pct}</text>"""

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


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="Codeforces handle")
    parser.add_argument("--out",  default="generated")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"[1/4] Fetching user info for {args.user}...")
    user = fetch_user_info(args.user)
    print(f"      rating={user.get('rating') or 'unrated'}  rank={user.get('rank') or 'none'}")

    print("[2/4] Fetching contest history...")
    contests = fetch_user_rating(args.user)
    print(f"      contests={len(contests)}")

    print("[3/4] Fetching submissions...")
    submissions = fetch_user_submissions(args.user)
    print(f"      total submissions fetched: {len(submissions)}")

    stats = build_stats(submissions)
    print(f"      unique solved   : {stats['total_solved']}")
    print(f"      current streak  : {stats['current_streak']} days")
    print(f"      max streak      : {stats['max_streak']} days")
    print(f"      top tags        : { {t: stats['tags'].get(t,0) for t in TRACKED_TAGS} }")

    print("[4/4] Generating SVGs...")

    with open(os.path.join(args.out, "codeforces_overview.svg"), "w", encoding="utf-8") as f:
        f.write(make_overview_svg(user, stats, contests))
    print(f"      ✓ codeforces_overview.svg")

    with open(os.path.join(args.out, "codeforces_tags.svg"), "w", encoding="utf-8") as f:
        f.write(make_tags_svg(stats, user))
    print(f"      ✓ codeforces_tags.svg")

    print("\nDone.")


if __name__ == "__main__":
    main()
