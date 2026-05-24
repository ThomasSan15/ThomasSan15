#!/usr/bin/env python3
"""
CSES Stats SVG Generator for GitHub README
Scrapes your CSES profile and generates beautiful SVG cards.

Usage:
    python generate_cses_stats.py --user 416103 --username ThomasBA

Required packages:
    pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
import os
import sys
import argparse
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Full CSES problem set categories and their total problem counts
# Source: https://cses.fi/problemset/
CATEGORIES = {
    "Introductory Problems":  19,
    "Sorting and Searching":  35,
    "Dynamic Programming":    19,
    "Graph Algorithms":       36,
    "Range Queries":          19,
    "Tree Algorithms":        16,
    "Mathematics":            31,
    "String Algorithms":      17,
    "Geometry":               7,
    "Advanced Techniques":    24,
    "Additional Problems":    77,
}
TOTAL_PROBLEMS = sum(CATEGORIES.values())  # 300

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ─── SCRAPER ───────────────────────────────────────────────────────────────────

def fetch_user_stats(user_id: str) -> dict:
    """Fetch basic stats from the CSES user page."""
    url = f"https://cses.fi/user/{user_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    stats = {
        "username": "Unknown",
        "submission_count": 0,
        "first_submission": "N/A",
        "last_submission": "N/A",
        "languages": {},
    }

    # Username
    h1 = soup.find("h1")
    if h1:
        stats["username"] = h1.text.replace("User ", "").strip()

    # Parse info table
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                label = cols[0].text.strip().lower()
                value = cols[1].text.strip()
                if "submission count" in label:
                    try:
                        stats["submission_count"] = int(value)
                    except ValueError:
                        pass
                elif "first submission" in label:
                    stats["first_submission"] = value[:10]
                elif "last submission" in label:
                    stats["last_submission"] = value[:10]
                elif "language" in label and "number" not in label:
                    # Language table row
                    pass

    # Languages sub-table
    for table in tables:
        headers_row = table.find("tr")
        if headers_row:
            ths = [th.text.strip().lower() for th in headers_row.find_all("th")]
            if "language" in ths and "number of submissions" in " ".join(ths):
                for row in table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        lang = cols[0].text.strip()
                        try:
                            count = int(cols[1].text.strip())
                            stats["languages"][lang] = count
                        except ValueError:
                            pass

    return stats


def fetch_solved_problems(user_id: str) -> dict:
    """
    Fetch per-category solved counts from the CSES problemset user page.
    Returns dict: { category_name: solved_count }
    """
    url = f"https://cses.fi/problemset/user/{user_id}/"
    solved = {cat: 0 for cat in CATEGORIES}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [warn] Could not fetch per-category data (status {resp.status_code}). Using totals only.")
            return solved

        soup = BeautifulSoup(resp.text, "html.parser")

        # Each category section has an <h2> followed by problem links.
        # Solved problems have class "full" on their <a> tag.
        current_cat = None
        for tag in soup.find_all(["h2", "a"]):
            if tag.name == "h2":
                text = tag.text.strip()
                # Match to our known categories
                for cat in CATEGORIES:
                    if cat.lower() in text.lower():
                        current_cat = cat
                        break
                else:
                    current_cat = None
            elif tag.name == "a" and current_cat:
                classes = tag.get("class", [])
                if "full" in classes:
                    solved[current_cat] = solved.get(current_cat, 0) + 1

    except Exception as e:
        print(f"  [warn] Per-category fetch failed: {e}")

    return solved


# ─── SVG GENERATORS ────────────────────────────────────────────────────────────

def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def make_overview_svg(stats: dict, total_solved: int) -> str:
    """Generate the top-level overview SVG card."""
    username = stats["username"]
    submissions = stats["submission_count"]
    last_sub = stats["last_submission"]
    first_sub = stats["first_submission"]
    pct = clamp(round(total_solved / TOTAL_PROBLEMS * 100, 1), 0, 100)
    bar_w = clamp(int(total_solved / TOTAL_PROBLEMS * 340), 0, 340)
    generated = datetime.utcnow().strftime("%Y-%m-%d")

    return f"""<svg width="420" height="190" viewBox="0 0 420 190"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="CSES Stats for {username}">
  <title>CSES Stats – {username}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#161b22"/>
    </linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#c9373c"/>
      <stop offset="100%" stop-color="#ff6b6b"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#c9373c" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#c9373c" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="round"><rect width="420" height="190" rx="12"/></clipPath>
  </defs>

  <!-- Background -->
  <rect width="420" height="190" rx="12" fill="url(#bg)" clip-path="url(#round)"/>
  <rect width="140" height="190" fill="url(#accent)" clip-path="url(#round)"/>

  <!-- Red left border -->
  <rect width="3" height="190" rx="2" fill="#c9373c"/>

  <!-- Header -->
  <text x="20" y="34" font-family="JetBrains Mono,monospace" font-size="13"
        fill="#c9373c" font-weight="700" letter-spacing="2">CSES PROBLEM SET</text>
  <text x="20" y="56" font-family="JetBrains Mono,monospace" font-size="18"
        fill="#e6edf3" font-weight="700">{username}</text>

  <!-- Divider -->
  <line x1="20" y1="68" x2="400" y2="68" stroke="#30363d" stroke-width="1"/>

  <!-- Stats row -->
  <text x="20"  y="92" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">SOLVED</text>
  <text x="130" y="92" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">SUBMISSIONS</text>
  <text x="280" y="92" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">LAST ACTIVE</text>

  <text x="20"  y="112" font-family="JetBrains Mono,monospace" font-size="22" fill="#e6edf3" font-weight="700">{total_solved}<tspan font-size="12" fill="#8b949e">/{TOTAL_PROBLEMS}</tspan></text>
  <text x="130" y="112" font-family="JetBrains Mono,monospace" font-size="22" fill="#e6edf3" font-weight="700">{submissions}</text>
  <text x="280" y="112" font-family="JetBrains Mono,monospace" font-size="13" fill="#c9d1d9">{last_sub}</text>

  <!-- Progress bar track -->
  <rect x="20" y="130" width="380" height="8" rx="4" fill="#21262d"/>
  <!-- Progress bar fill -->
  <rect x="20" y="130" width="{bar_w}" height="8" rx="4" fill="url(#bar)">
    <animate attributeName="width" from="0" to="{bar_w}" dur="1.2s" fill="freeze" calcMode="spline"
             keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>

  <!-- Percentage label -->
  <text x="20" y="158" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9373c" font-weight="600">{pct}% complete</text>
  <text x="390" y="158" font-family="JetBrains Mono,monospace" font-size="10" fill="#484f58" text-anchor="end">since {first_sub}</text>

  <!-- Footer -->
  <text x="20" y="180" font-family="JetBrains Mono,monospace" font-size="9" fill="#484f58">updated {generated} UTC · cses.fi/user/{stats.get("user_id","")}</text>
</svg>"""


def make_categories_svg(solved: dict) -> str:
    """Generate the per-category progress bars SVG."""
    # Only include the 8 most interesting categories (skip Additional)
    display_cats = [
        ("Introductory",   "Introductory Problems"),
        ("Sorting",        "Sorting and Searching"),
        ("DP",             "Dynamic Programming"),
        ("Graphs",         "Graph Algorithms"),
        ("Range Queries",  "Range Queries"),
        ("Trees",          "Tree Algorithms"),
        ("Math",           "Mathematics"),
        ("Strings",        "String Algorithms"),
    ]

    row_h   = 28
    padding = 16
    height  = padding * 2 + len(display_cats) * row_h + 40  # header
    bar_max = 240

    rows_svg = ""
    for i, (short, full) in enumerate(display_cats):
        s = solved.get(full, 0)
        t = CATEGORIES.get(full, 1)
        pct = s / t
        bar_w = clamp(int(pct * bar_max), 0, bar_max)
        y = padding + 40 + i * row_h
        label_color = "#c9373c" if pct >= 1.0 else "#8b949e"
        count_str = f"{s}/{t}"

        rows_svg += f"""
  <!-- {full} -->
  <text x="16" y="{y + 12}" font-family="JetBrains Mono,monospace" font-size="11"
        fill="#c9d1d9">{short}</text>
  <rect x="110" y="{y + 3}" width="{bar_max}" height="10" rx="5" fill="#21262d"/>
  <rect x="110" y="{y + 3}" width="{bar_w}" height="10" rx="5" fill="#c9373c" opacity="0.9">
    <animate attributeName="width" from="0" to="{bar_w}" dur="{1.0 + i * 0.08:.2f}s" fill="freeze"
             calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{110 + bar_max + 8}" y="{y + 12}" font-family="JetBrains Mono,monospace"
        font-size="10" fill="{label_color}">{count_str}</text>"""

    return f"""<svg width="420" height="{height}" viewBox="0 0 420 {height}"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="CSES Category Progress">
  <title>CSES Category Progress</title>
  <defs>
    <clipPath id="round2"><rect width="420" height="{height}" rx="12"/></clipPath>
  </defs>

  <!-- Background -->
  <rect width="420" height="{height}" rx="12" fill="#0d1117" clip-path="url(#round2)"/>
  <rect width="3" height="{height}" rx="2" fill="#c9373c"/>

  <!-- Header -->
  <text x="16" y="26" font-family="JetBrains Mono,monospace" font-size="11"
        fill="#c9373c" font-weight="700" letter-spacing="2">CATEGORY PROGRESS</text>
  <line x1="16" y1="36" x2="404" y2="36" stroke="#21262d" stroke-width="1"/>

  {rows_svg}
</svg>"""


def make_language_svg(stats: dict) -> str:
    """Generate a small languages badge SVG."""
    langs = stats.get("languages", {})
    if not langs:
        langs = {"C++": 100}

    total = sum(langs.values()) or 1
    items = sorted(langs.items(), key=lambda x: -x[1])[:5]

    LANG_COLORS = {
        "C++": "#00599C",
        "Python": "#3572A5",
        "Java": "#B07219",
        "Rust": "#B7410E",
        "Go": "#00ADD8",
        "C": "#555555",
    }

    w = 420
    row_h = 24
    h = 16 + 30 + len(items) * row_h + 16

    rows = ""
    for i, (lang, count) in enumerate(items):
        pct = count / total * 100
        bar_w = int(pct / 100 * 340)
        color = LANG_COLORS.get(lang, "#888888")
        y = 46 + i * row_h
        rows += f"""
  <circle cx="16" cy="{y + 5}" r="5" fill="{color}"/>
  <text x="28" y="{y + 10}" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9d1d9">{lang}</text>
  <rect x="110" y="{y}" width="{bar_w}" height="10" rx="5" fill="{color}" opacity="0.75"/>
  <text x="460" y="{y + 10}" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e" text-anchor="end">{pct:.0f}%</text>"""

    return f"""<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="CSES Languages">
  <title>CSES Languages</title>
  <defs><clipPath id="rl"><rect width="{w}" height="{h}" rx="12"/></clipPath></defs>
  <rect width="{w}" height="{h}" rx="12" fill="#0d1117" clip-path="url(#rl)"/>
  <rect width="3" height="{h}" rx="2" fill="#c9373c"/>
  <text x="16" y="22" font-family="JetBrains Mono,monospace" font-size="11"
        fill="#c9373c" font-weight="700" letter-spacing="2">LANGUAGES USED</text>
  <line x1="16" y1="30" x2="{w - 16}" y2="30" stroke="#21262d" stroke-width="1"/>
  {rows}
</svg>"""


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate CSES stats SVGs")
    parser.add_argument("--user",     required=True, help="CSES numeric user ID (e.g. 416103)")
    parser.add_argument("--username", required=True, help="CSES display username (e.g. ThomasBA)")
    parser.add_argument("--out",      default="generated", help="Output directory for SVGs")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"[1/3] Fetching user stats for {args.username} (id={args.user})...")
    stats = fetch_user_stats(args.user)
    stats["user_id"] = args.user
    print(f"      Submissions: {stats['submission_count']}, Last: {stats['last_submission']}")

    print("[2/3] Fetching per-category solved counts...")
    solved = fetch_solved_problems(args.user)
    total_solved = sum(solved.values())
    print(f"      Total solved: {total_solved}/{TOTAL_PROBLEMS}")
    for cat, s in solved.items():
        if s > 0:
            print(f"      {cat}: {s}/{CATEGORIES[cat]}")

    print("[3/3] Generating SVGs...")

    overview_path = os.path.join(args.out, "cses_overview.svg")
    with open(overview_path, "w", encoding="utf-8") as f:
        f.write(make_overview_svg(stats, total_solved))
    print(f"      ✓ {overview_path}")

    cats_path = os.path.join(args.out, "cses_categories.svg")
    with open(cats_path, "w", encoding="utf-8") as f:
        f.write(make_categories_svg(solved))
    print(f"      ✓ {cats_path}")

    lang_path = os.path.join(args.out, "cses_languages.svg")
    with open(lang_path, "w", encoding="utf-8") as f:
        f.write(make_language_svg(stats))
    print(f"      ✓ {lang_path}")

    # Also keep backward-compat with old cses_solved.svg
    solved_path = os.path.join(args.out, "cses_solved.svg")
    with open(solved_path, "w", encoding="utf-8") as f:
        f.write(make_overview_svg(stats, total_solved))
    print(f"      ✓ {solved_path} (backward-compat alias)")

    print("\nDone! Paste the following into your README:\n")
    print("<!-- CSES Stats -->")
    print(f'<img src="https://raw.githubusercontent.com/ThomasSan15/ThomasSan15/main/generated/cses_overview.svg" width="420"/>')
    print(f'<img src="https://raw.githubusercontent.com/ThomasSan15/ThomasSan15/main/generated/cses_categories.svg" width="420"/>')


if __name__ == "__main__":
    main()
