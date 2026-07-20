#!/usr/bin/env python3
"""
LeetCode Stats SVG Card Generator
Generates:
  generated/leetcode_overview.svg
  generated/leetcode_difficulty.svg
  generated/leetcode_topics.svg
Usage:
    python scripts/generate_leetcode_stats.py --user ThomasSan15
"""
from __future__ import annotations
import math, os, sys, time, argparse, requests
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG      = "#0d1117"
C_BG2     = "#111827"
C_BORDER  = "#21262d"
C_LINE    = "#1c2128"
C_TRACK   = "#161b22"
C_TEXT1   = "#e6edf3"
C_TEXT2   = "#8b949e"
C_TEXT3   = "#484f58"
C_ACCENT  = "#d4a017"   # premium gold — primary
C_ACCENT2 = "#f0c14b"   # soft gold    — secondary
C_EASY    = "#2cbe4e"
C_MEDIUM  = "#f0a500"
C_HARD    = "#ef4743"

# LeetCode totals (fetched live, these are fallbacks)
LC_TOTAL_EASY   = 862
LC_TOTAL_MEDIUM = 1805
LC_TOTAL_HARD   = 784
LC_TOTAL        = LC_TOTAL_EASY + LC_TOTAL_MEDIUM + LC_TOTAL_HARD

LEETCODE_GQL = "https://leetcode.com/graphql"
GQL_HEADERS  = {
    "Content-Type": "application/json",
    "Referer":      "https://leetcode.com",
    "User-Agent":   (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Exactly 14 topics as requested
TRACKED_TOPICS = [
    "Array", "String", "Hash Table", "Dynamic Programming",
    "Greedy", "Binary Search", "Graph", "Tree", "Math",
    "Sorting", "Two Pointers", "Sliding Window", "Prefix Sum", "Backtracking",
]

TOPIC_LABELS: dict[str, str] = {
    "Array":               "Array",
    "String":              "String",
    "Hash Table":          "Hash Table",
    "Dynamic Programming": "Dynamic Programming",
    "Greedy":              "Greedy",
    "Binary Search":       "Binary Search",
    "Graph":               "Graph",
    "Tree":                "Tree",
    "Math":                "Math",
    "Sorting":             "Sorting",
    "Two Pointers":        "Two Pointers",
    "Sliding Window":      "Sliding Window",
    "Prefix Sum":          "Prefix Sum",
    "Backtracking":        "Backtracking",
}


# ── GraphQL ───────────────────────────────────────────────────────────────────

Q_PROFILE = """query($username:String!){matchedUser(username:$username){
  username profile{ranking}
  submitStats:submitStatsGlobal{acSubmissionNum{difficulty count submissions}}
  activeBadge{displayName}
  streak:activeDailyChallengeStreak{currentStreak longestStreak}
}}"""

Q_TAGS = """query($username:String!){matchedUser(username:$username){
  tagProblemCounts{
    advanced{tagName problemsSolved}
    intermediate{tagName problemsSolved}
    fundamental{tagName problemsSolved}
  }
}}"""

Q_CALENDAR = """query($username:String!,$year:Int){matchedUser(username:$username){
  userCalendar(year:$year){streak totalActiveDays}
}}"""

Q_TOTALS = """query{allQuestionsCount{difficulty count}}"""


def gql(query: str, variables: dict = {}, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.post(LEETCODE_GQL,
                json={"query": query, "variables": variables},
                headers=GQL_HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data.get("data", {})
        except Exception as exc:
            if attempt == retries - 1: raise
            time.sleep(1.5 ** attempt)
            print(f"      [retry {attempt+1}] {exc}")
    return {}


def fetch_all(username: str) -> dict:
    year = datetime.now(timezone.utc).year
    print("      → profile & submit stats...")
    d1   = gql(Q_PROFILE,  {"username": username})
    user = d1.get("matchedUser") or {}
    print("      → topic tag counts...")
    d2      = gql(Q_TAGS,  {"username": username})
    tagdata = ((d2.get("matchedUser") or {}).get("tagProblemCounts")) or {}
    print("      → activity calendar...")
    d3  = gql(Q_CALENDAR, {"username": username, "year": year})
    cal = ((d3.get("matchedUser") or {}).get("userCalendar")) or {}
    print("      → global totals...")
    try:
        d4     = gql(Q_TOTALS)
        totals = {r["difficulty"]: r["count"] for r in (d4.get("allQuestionsCount") or [])}
    except Exception:
        totals = {}
    return {"user": user, "tags": tagdata, "calendar": cal, "totals": totals}


def parse_ac(user: dict) -> dict:
    rows   = (user.get("submitStats") or {}).get("acSubmissionNum") or []
    result = {d: {"count": 0, "submissions": 0}
              for d in ("All", "Easy", "Medium", "Hard")}
    for row in rows:
        d = row.get("difficulty", "All")
        if d in result:
            result[d]["count"]       = row.get("count", 0)
            result[d]["submissions"] = row.get("submissions", 0)
    return result


def parse_tags(tagdata: dict) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for tier in ("fundamental", "intermediate", "advanced"):
        for item in tagdata.get(tier) or []:
            n = item.get("tagName", "")
            v = item.get("problemsSolved", 0)
            if n and v:
                counts[n] += v
    return dict(counts)


def get_totals(raw: dict) -> tuple:
    e = raw.get("Easy",   LC_TOTAL_EASY)
    m = raw.get("Medium", LC_TOTAL_MEDIUM)
    h = raw.get("Hard",   LC_TOTAL_HARD)
    return e, m, h, e + m + h


# ── SVG primitives ────────────────────────────────────────────────────────────

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def bw(count: int, total: int, max_px: int) -> int:
    return int(clamp(count / max(total, 1) * max_px, 0, max_px))

def pct(count: int, total: int) -> str:
    return "0%" if total == 0 else f"{count/total*100:.1f}%"

def tx(x, y, text, size=11, fill=C_TEXT1, weight="400",
       anchor="start", spacing="") -> str:
    sp = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x}" y="{y}" font-family="JetBrains Mono,monospace" '
            f'font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{sp}>{text}</text>')

def abar(x, y, w_max, h, rx, fill_w, color, dur="1.2s") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w_max}" height="{h}" rx="{rx}" fill="{C_TRACK}"/>\n'
        f'<rect x="{x}" y="{y}" width="{fill_w}" height="{h}" rx="{rx}" '
        f'fill="{color}" opacity="0.9">\n'
        f'  <animate attributeName="width" from="0" to="{fill_w}" dur="{dur}"\n'
        f'           fill="freeze" calcMode="spline"\n'
        f'           keySplines="0.4 0 0.2 1" keyTimes="0;1"/>\n'
        f'</rect>'
    )

def shell(W, H, sid, accent=C_ACCENT) -> str:
    return (
        f'<defs>\n'
        f'  <linearGradient id="bg{sid}" x1="0" y1="0" x2="0" y2="1">\n'
        f'    <stop offset="0%" stop-color="{C_BG}"/>\n'
        f'    <stop offset="100%" stop-color="{C_BG2}"/>\n'
        f'  </linearGradient>\n'
        f'  <filter id="glow{sid}">\n'
        f'    <feGaussianBlur stdDeviation="2.5" result="b"/>\n'
        f'    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
        f'  </filter>\n'
        f'  <clipPath id="clip{sid}"><rect width="{W}" height="{H}" rx="12"/></clipPath>\n'
        f'</defs>\n'
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg{sid})" clip-path="url(#clip{sid})"/>\n'
        f'<rect width="{W}" height="2" fill="{accent}" opacity="0.85"/>\n'
        f'<rect width="3" height="{H}" fill="{accent}"/>\n'
        f'<rect width="{W}" height="{H}" rx="12" fill="none" stroke="{C_BORDER}" stroke-width="1"/>'
    )

def hdr(W, eyebrow, title, ts, accent=C_ACCENT) -> str:
    return (
        tx(20, 20, eyebrow, size=10, fill=accent, weight="700", spacing="2") + "\n"
        + tx(20, 38, title, size=17, fill=C_TEXT1, weight="700") + "\n"
        + tx(W-14, 20, ts, size=8, fill=C_TEXT3, anchor="end") + "\n"
        + f'<line x1="20" y1="48" x2="{W-14}" y2="48" stroke="{C_LINE}" stroke-width="1"/>'
    )

def ring_svg(cx, cy, r, pct_val, sid, color=C_ACCENT) -> str:
    c   = 2 * math.pi * r
    on  = clamp(pct_val, 0, 1) * c
    off = c - on
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{C_LINE}" stroke-width="7"/>\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
        f'stroke-width="7" opacity="0.07"/>\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
        f'stroke-width="7" stroke-dasharray="{on:.2f} {off:.2f}" stroke-linecap="round" '
        f'transform="rotate(-90 {cx} {cy})" filter="url(#glow{sid})">\n'
        f'  <animate attributeName="stroke-dasharray" from="0 {c:.2f}" '
        f'to="{on:.2f} {off:.2f}" dur="1.5s" fill="freeze" calcMode="spline" '
        f'keySplines="0.4 0 0.2 1" keyTimes="0;1"/>\n'
        f'</circle>'
    )


# ── Card 1: Overview ──────────────────────────────────────────────────────────

def make_overview(username: str, user: dict, ac: dict, cal: dict, totals: tuple) -> str:
    _, _, _, lc_total = totals
    ranking    = (user.get("profile") or {}).get("ranking") or 0
    total_s    = ac["All"]["count"]
    total_sub  = ac["All"]["submissions"]
    acc        = pct(total_s, total_sub)
    sk         = user.get("streak") or {}
    cur_streak = sk.get("currentStreak") or cal.get("streak") or 0
    lon_streak = sk.get("longestStreak") or 0
    act_days   = cal.get("totalActiveDays") or 0
    ts         = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    ring_cx, ring_cy, ring_r = 66, 116, 46
    bar_tgt = max(500, ((total_s // 500) + 1) * 500)
    B_MAX   = 300
    W, H    = 470, 228

    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"\n'
        f'     xmlns="http://www.w3.org/2000/svg" role="img"\n'
        f'     aria-label="LeetCode Overview - {username}">\n'
        f'  <title>LeetCode Overview - {username}</title>\n'
        + shell(W, H, "lc1") + "\n"
        + hdr(W, "LEETCODE", username, ts) + "\n"
        + ring_svg(ring_cx, ring_cy, ring_r, total_s/max(lc_total,1), "lc1") + "\n"
        + tx(ring_cx, ring_cy-10, str(total_s), size=20, fill=C_TEXT1, weight="700", anchor="middle") + "\n"
        + tx(ring_cx, ring_cy+7,  "SOLVED", size=8, fill=C_ACCENT, weight="700", anchor="middle", spacing="1.5") + "\n"
        + tx(ring_cx, ring_cy+22, f"/ {lc_total}", size=8, fill=C_TEXT3, anchor="middle") + "\n"
        + tx(148, 68,  "RANKING",     size=9, fill=C_TEXT2, spacing="1") + "\n"
        + tx(300, 68,  "ACCEPTANCE",  size=9, fill=C_TEXT2, spacing="1") + "\n"
        + tx(148, 86,  f"#{ranking:,}" if ranking else "-", size=16, fill=C_TEXT1, weight="700") + "\n"
        + tx(300, 86,  acc, size=16, fill=C_TEXT1, weight="700") + "\n"
        + tx(148, 110, "AC STREAK",   size=9, fill=C_TEXT2, spacing="1") + "\n"
        + tx(300, 110, "BEST STREAK", size=9, fill=C_TEXT2, spacing="1") + "\n"
        + f'<text x="148" y="128" font-family="JetBrains Mono,monospace" font-size="20" '
          f'fill="{C_TEXT1}" font-weight="700">{cur_streak}'
          f'<tspan font-size="10" fill="{C_TEXT2}"> d</tspan></text>\n'
        + f'<text x="300" y="128" font-family="JetBrains Mono,monospace" font-size="20" '
          f'fill="{C_TEXT1}" font-weight="700">{lon_streak}'
          f'<tspan font-size="10" fill="{C_TEXT2}"> d</tspan></text>\n'
        + tx(148, 152, "SUBMISSIONS", size=9, fill=C_TEXT2, spacing="1") + "\n"
        + tx(300, 152, "ACTIVE DAYS", size=9, fill=C_TEXT2, spacing="1") + "\n"
        + tx(148, 168, f"{total_sub:,}", size=15, fill=C_TEXT1, weight="700") + "\n"
        + tx(300, 168, str(act_days),    size=15, fill=C_TEXT1, weight="700") + "\n"
        + f'<line x1="20" y1="192" x2="{W-14}" y2="192" stroke="{C_LINE}" stroke-width="1"/>\n'
        + tx(20,  207, "solved progress", size=8, fill=C_TEXT3) + "\n"
        + abar(120, 200, B_MAX, 5, 2, bw(total_s, bar_tgt, B_MAX), C_ACCENT) + "\n"
        + tx(W-14, 207, f"{total_s}/{bar_tgt}", size=8, fill=C_TEXT3, anchor="end") + "\n"
        + "</svg>"
    )


# ── Card 2: Difficulty ────────────────────────────────────────────────────────

def make_difficulty(username: str, ac: dict, totals: tuple, streak: int = 0) -> str:
    t_easy, t_med, t_hard, t_all = totals
    total_s = ac["All"]["count"]
    ts      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    BAR_X   = 152
    BAR_W   = 196
    W       = 430

    ring_cx, ring_cy, ring_r = 66, 128, 46

    diffs = [
        ("EASY",   ac["Easy"]["count"],   t_easy,  C_EASY),
        ("MEDIUM", ac["Medium"]["count"], t_med,   C_MEDIUM),
        ("HARD",   ac["Hard"]["count"],   t_hard,  C_HARD),
    ]

    # 3 diff rows (52px each, starting y=64) + streak row after = 64+3*52+52 = 272 content
    # Total card height: 232 base + 52 streak = 284
    H = 286

    # Build difficulty rows
    diff_parts = []
    for i, (label, solved, total, color) in enumerate(diffs):
        y      = 64 + i * 52
        dur    = f"{1.1 + i*0.15:.2f}s"
        bw_val = bw(solved, total, BAR_W)
        p_val  = pct(solved, total)
        diff_parts.append(
            tx(BAR_X, y, label, size=9, fill=color, weight="700", spacing="1") + "\n"
            + abar(BAR_X, y+7, BAR_W, 10, 5, bw_val, color, dur=dur) + "\n"
            + f'<text x="{BAR_X+BAR_W+8}" y="{y+16}" font-family="JetBrains Mono,monospace" '
              f'font-size="12" fill="{color}" font-weight="700">{solved}</text>\n'
            + f'<text x="{BAR_X+BAR_W+50}" y="{y+16}" font-family="JetBrains Mono,monospace" '
              f'font-size="9" fill="{C_TEXT3}" text-anchor="end">{p_val}</text>\n'
            + tx(BAR_X, y+30, f"/ {total:,} total", size=8, fill=C_TEXT3)
        )
    diff_svg = "\n".join(diff_parts)

    # Streak row — naturally continues after Hard row
    sk_y = 64 + 3 * 52   # = 220
    streak_svg = (
        f'<line x1="{BAR_X}" y1="{sk_y - 6}" x2="{W-14}" y2="{sk_y - 6}" '
        f'stroke="{C_LINE}" stroke-width="1"/>\n'
        + tx(BAR_X, sk_y+12, "AC STREAK", size=9, fill=C_TEXT2, spacing="1") + "\n"
        + f'<text x="{BAR_X}" y="{sk_y+32}" font-family="JetBrains Mono,monospace" '
          f'font-size="18" fill="{C_TEXT1}" font-weight="700">{streak}'
          f'<tspan font-size="10" fill="{C_TEXT2}"> days</tspan></text>'
    )

    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"\n'
        f'     xmlns="http://www.w3.org/2000/svg" role="img"\n'
        f'     aria-label="LeetCode Difficulty - {username}">\n'
        f'  <title>LeetCode Difficulty - {username}</title>\n'
        + shell(W, H, "lc2", C_ACCENT2) + "\n"
        + hdr(W, "DIFFICULTY", username, ts, C_ACCENT2) + "\n"
        + ring_svg(ring_cx, ring_cy, ring_r, total_s/max(t_all,1), "lc2", C_ACCENT2) + "\n"
        + tx(ring_cx, ring_cy-10, str(total_s), size=18, fill=C_TEXT1, weight="700", anchor="middle") + "\n"
        + tx(ring_cx, ring_cy+7,  "SOLVED", size=8, fill=C_ACCENT2, weight="700", anchor="middle", spacing="1.5") + "\n"
        + tx(ring_cx, ring_cy+22, f"/ {t_all}", size=8, fill=C_TEXT3, anchor="middle") + "\n"
        + diff_svg + "\n"
        + streak_svg + "\n"
        + "</svg>"
    )


# ── Card 3: Topics ────────────────────────────────────────────────────────────

def make_topics(username: str, topic_counts: dict[str, int], total_solved: int) -> str:
    ts    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows  = sorted(
        [(tp, topic_counts.get(tp, 0)) for tp in TRACKED_TOPICS],
        key=lambda x: -x[1],
    )
    max_c = max((r[1] for r in rows), default=1) or 1
    denom = max(total_solved, 1)

    BAR_X = 164
    BAR_W = 192
    ROW_H = 30
    PAD   = 16
    HDR_H = 52
    W     = 430
    H     = PAD * 2 + HDR_H + len(rows) * ROW_H

    parts = []
    for i, (topic, count) in enumerate(rows):
        fw         = int(clamp(count / max_c * BAR_W, 0, BAR_W))
        p          = f"{count/denom*100:.0f}%"
        y          = PAD + HDR_H + i * ROW_H
        dur        = f"{1.0 + i*0.055:.2f}s"
        label      = TOPIC_LABELS.get(topic, topic)
        bar_color  = C_ACCENT if count == max_c else "#2a3f5f"
        text_color = C_ACCENT if count == max_c else C_TEXT2

        parts.append(
            tx(16, y+16, label, size=11, fill="#c9d1d9") + "\n"
            + abar(BAR_X, y+7, BAR_W, 10, 5, fw, bar_color, dur=dur) + "\n"
            + f'<text x="{BAR_X+BAR_W+8}" y="{y+16}" font-family="JetBrains Mono,monospace" '
              f'font-size="10" fill="{text_color}" font-weight="700">{count}</text>\n'
            + f'<text x="{BAR_X+BAR_W+42}" y="{y+16}" font-family="JetBrains Mono,monospace" '
              f'font-size="9" fill="{C_TEXT3}" text-anchor="end">{p}</text>'
        )

    body = "\n".join(parts)

    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"\n'
        f'     xmlns="http://www.w3.org/2000/svg" role="img"\n'
        f'     aria-label="LeetCode Topics - {username}">\n'
        f'  <title>LeetCode Topics - {username}</title>\n'
        + shell(W, H, "lc3") + "\n"
        + hdr(W, "TOPIC STATS", username, ts) + "\n"
        + body + "\n"
        + "</svg>"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--out",  default="generated")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    u = args.user

    print(f"[1/4] Fetching LeetCode data for {u}...")
    fetched = fetch_all(u)

    user_data = fetched["user"]
    if not user_data:
        print(f"[error] User '{u}' not found or LeetCode API unavailable.")
        sys.exit(1)

    ac          = parse_ac(user_data)
    tag_counts  = parse_tags(fetched["tags"])
    cal         = fetched["calendar"]
    totals      = get_totals(fetched["totals"])
    sk          = user_data.get("streak") or {}
    cur_streak  = sk.get("currentStreak") or cal.get("streak") or 0

    print(f"      solved={ac['All']['count']}  easy={ac['Easy']['count']}  "
          f"medium={ac['Medium']['count']}  hard={ac['Hard']['count']}")
    print(f"      streak={cur_streak}  active_days={cal.get('totalActiveDays', 0)}")

    print("[2/4] Generating overview SVG...")
    svg1 = make_overview(u, user_data, ac, cal, totals)

    print("[3/4] Generating difficulty SVG...")
    svg2 = make_difficulty(u, ac, totals, streak=cur_streak)

    print("[4/4] Generating topics SVG...")
    svg3 = make_topics(u, tag_counts, ac["All"]["count"])

    for name, svg in [
        ("leetcode_overview.svg",   svg1),
        ("leetcode_difficulty.svg", svg2),
        ("leetcode_topics.svg",     svg3),
    ]:
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"      ✓ {path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
