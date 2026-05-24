#!/usr/bin/env python3
"""
CSES Stats SVG Generator
Lee la cookie desde la variable de entorno CSES_SESSION.
"""

import requests
from bs4 import BeautifulSoup
import os
import argparse
from datetime import datetime

CATEGORIES = {
    "Introductory Problems":  19,
    "Sorting and Searching":  35,
    "Dynamic Programming":    19,
    "Graph Algorithms":       36,
    "Range Queries":          19,
    "Tree Algorithms":        16,
    "Mathematics":            31,
    "String Algorithms":      17,
    "Geometry":                7,
    "Advanced Techniques":    24,
    "Additional Problems":    77,
}
TOTAL_PROBLEMS = sum(CATEGORIES.values())  # 300

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    cookie_val = os.getenv("CSES_SESSION", "").strip()
    if not cookie_val:
        print("[warn] CSES_SESSION no está definida. Las categorías mostrarán 0.")
        return session

    # Acepta tanto "PHPSESSID=abc123" como solo "abc123"
    if cookie_val.startswith("PHPSESSID="):
        cookie_val = cookie_val.split("=", 1)[1]

    session.cookies.set("PHPSESSID", cookie_val, domain="cses.fi")
    print(f"[info] Cookie cargada ({len(cookie_val)} chars).")
    return session


def fetch_user_stats(session: requests.Session, user_id: str) -> dict:
    url = f"https://cses.fi/user/{user_id}"
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    stats = {
        "username": "ThomasBA",
        "submission_count": 0,
        "first_submission": "N/A",
        "last_submission": "N/A",
        "languages": {},
        "user_id": user_id,
    }

    h1 = soup.find("h1")
    if h1:
        stats["username"] = h1.text.replace("User ", "").strip()

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
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

        # Tabla de lenguajes
        header_row = table.find("tr")
        if header_row:
            ths = [th.text.strip().lower() for th in header_row.find_all("th")]
            if "language" in ths:
                for row in table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        lang = cols[0].text.strip()
                        try:
                            stats["languages"][lang] = int(cols[1].text.strip())
                        except ValueError:
                            pass
    return stats


def fetch_solved_problems(user_id: str) -> dict:
    """
    Fetch solved problems and map them to categories using task IDs.
    """

    url = f"https://cses.fi/problemset/user/{user_id}/"

    solved = {cat: 0 for cat in CATEGORIES}

    # Task ID -> Category
    TASK_CATEGORY = {
        # Introductory
        1068: "Introductory Problems",
        1083: "Introductory Problems",
        1069: "Introductory Problems",
        1094: "Introductory Problems",
        1070: "Introductory Problems",
        1071: "Introductory Problems",
        1072: "Introductory Problems",
        1092: "Introductory Problems",
        1617: "Introductory Problems",
        1618: "Introductory Problems",
        1754: "Introductory Problems",
        2205: "Introductory Problems",
        2165: "Introductory Problems",
        2168: "Introductory Problems",
        1755: "Introductory Problems",
        2205: "Introductory Problems",
        1097: "Dynamic Programming",

        # Sorting and Searching
        1621: "Sorting and Searching",
        1084: "Sorting and Searching",
        1090: "Sorting and Searching",
        1085: "Sorting and Searching",

        # Dynamic Programming
        1633: "Dynamic Programming",
        1634: "Dynamic Programming",
        1635: "Dynamic Programming",

        # Graph Algorithms
        1192: "Graph Algorithms",
        1193: "Graph Algorithms",
        1666: "Graph Algorithms",

        # Tree Algorithms
        1130: "Tree Algorithms",

        # Mathematics
        1619: "Mathematics",

        # String Algorithms
        1731: "String Algorithms",
    }

    try:
        session = requests.Session()

        session.cookies.set(
            "PHPSESSID",
            os.getenv("CSES_SESSION")
        )

        resp = session.get(url, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            print(f"[warn] status {resp.status_code}")
            return solved

        soup = BeautifulSoup(resp.text, "html.parser")

        solved_tasks = set()

        for a in soup.find_all("a", class_="full"):
            href = a.get("href", "")

            if "/problemset/task/" in href:
                try:
                    task_id = int(href.split("/task/")[1].split("/")[0])
                    solved_tasks.add(task_id)
                except:
                    pass

        for task_id in solved_tasks:
            if task_id in TASK_CATEGORY:
                cat = TASK_CATEGORY[task_id]
                solved[cat] += 1

    except Exception as e:
        print(f"[warn] Failed: {e}")

    return solved


# ── SVG ─────────────────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def make_overview_svg(stats: dict, total_solved: int) -> str:
    username    = stats["username"]
    submissions = stats["submission_count"]
    last_sub    = stats["last_submission"]
    first_sub   = stats["first_submission"]
    user_id     = stats["user_id"]
    pct         = clamp(round(total_solved / TOTAL_PROBLEMS * 100, 1), 0, 100)
    bar_w       = clamp(int(total_solved / TOTAL_PROBLEMS * 344), 0, 344)
    generated   = datetime.utcnow().strftime("%Y-%m-%d")

    return f"""<svg width="420" height="190" viewBox="0 0 420 190" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="CSES Stats for {username}">
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
      <stop offset="0%" stop-color="#c9373c" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#c9373c" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="cr"><rect width="420" height="190" rx="12"/></clipPath>
  </defs>
  <rect width="420" height="190" rx="12" fill="url(#bg)" clip-path="url(#cr)"/>
  <rect width="140" height="190" fill="url(#accent)" clip-path="url(#cr)"/>
  <rect width="3" height="190" fill="#c9373c"/>
  <text x="20" y="34" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9373c" font-weight="700" letter-spacing="2">CSES PROBLEM SET</text>
  <text x="20" y="54" font-family="JetBrains Mono,monospace" font-size="18" fill="#e6edf3" font-weight="700">{username}</text>
  <line x1="20" y1="66" x2="400" y2="66" stroke="#30363d" stroke-width="1"/>
  <text x="20"  y="86" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">SOLVED</text>
  <text x="140" y="86" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">SUBMISSIONS</text>
  <text x="280" y="86" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e">LAST ACTIVE</text>
  <text x="20"  y="110" font-family="JetBrains Mono,monospace" font-size="24" fill="#e6edf3" font-weight="700">{total_solved}<tspan font-size="13" fill="#8b949e">/{TOTAL_PROBLEMS}</tspan></text>
  <text x="140" y="110" font-family="JetBrains Mono,monospace" font-size="24" fill="#e6edf3" font-weight="700">{submissions}</text>
  <text x="280" y="110" font-family="JetBrains Mono,monospace" font-size="13" fill="#c9d1d9">{last_sub}</text>
  <rect x="20" y="126" width="380" height="8" rx="4" fill="#21262d"/>
  <rect x="20" y="126" width="{bar_w}" height="8" rx="4" fill="url(#bar)">
    <animate attributeName="width" from="0" to="{bar_w}" dur="1.2s" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="20"  y="152" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9373c" font-weight="600">{pct}% complete</text>
  <text x="400" y="152" font-family="JetBrains Mono,monospace" font-size="10" fill="#484f58" text-anchor="end">since {first_sub}</text>
  <text x="20"  y="176" font-family="JetBrains Mono,monospace" font-size="9"  fill="#484f58">updated {generated} UTC · cses.fi/user/{user_id}</text>
</svg>"""


def make_categories_svg(solved: dict) -> str:
    display = [
        ("Introductory",  "Introductory Problems"),
        ("Sorting",       "Sorting and Searching"),
        ("DP",            "Dynamic Programming"),
        ("Graphs",        "Graph Algorithms"),
        ("Range Queries", "Range Queries"),
        ("Trees",         "Tree Algorithms"),
        ("Math",          "Mathematics"),
        ("Strings",       "String Algorithms"),
    ]
    row_h   = 28
    pad     = 16
    height  = pad * 2 + 36 + len(display) * row_h
    bar_max = 244

    rows = ""
    for i, (short, full) in enumerate(display):
        s     = solved.get(full, 0)
        t     = CATEGORIES[full]
        bw    = clamp(int((s / t) * bar_max), 0, bar_max)
        y     = pad + 36 + i * row_h
        color = "#c9373c" if s >= t else "#8b949e"
        dur   = f"{1.0 + i * 0.08:.2f}s"
        rows += f"""
  <text x="16" y="{y+12}" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9d1d9">{short}</text>
  <rect x="110" y="{y+3}" width="{bar_max}" height="10" rx="5" fill="#21262d"/>
  <rect x="110" y="{y+3}" width="{bw}" height="10" rx="5" fill="#c9373c" opacity="0.9">
    <animate attributeName="width" from="0" to="{bw}" dur="{dur}" fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/>
  </rect>
  <text x="{110+bar_max+8}" y="{y+12}" font-family="JetBrains Mono,monospace" font-size="10" fill="{color}">{s}/{t}</text>"""

    return f"""<svg width="420" height="{height}" viewBox="0 0 420 {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="CSES Category Progress">
  <title>CSES Category Progress</title>
  <defs><clipPath id="cr2"><rect width="420" height="{height}" rx="12"/></clipPath></defs>
  <rect width="420" height="{height}" rx="12" fill="#0d1117" clip-path="url(#cr2)"/>
  <rect width="3" height="{height}" fill="#c9373c"/>
  <text x="16" y="24" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9373c" font-weight="700" letter-spacing="2">CATEGORY PROGRESS</text>
  <line x1="16" y1="33" x2="404" y2="33" stroke="#21262d" stroke-width="1"/>
  {rows}
</svg>"""


def make_language_svg(stats: dict) -> str:
    langs = stats.get("languages", {}) or {"C++": 100}
    total = sum(langs.values()) or 1
    items = sorted(langs.items(), key=lambda x: -x[1])[:5]
    LANG_COLORS = {
        "C++": "#00599C", "Python": "#3572A5", "Java": "#B07219",
        "Rust": "#B7410E", "Go": "#00ADD8", "C": "#555555",
    }
    w     = 420
    row_h = 24
    h     = 62 + len(items) * row_h

    rows = ""
    for i, (lang, count) in enumerate(items):
        pct   = count / total * 100
        bw    = int(pct / 100 * 280)
        color = LANG_COLORS.get(lang, "#888888")
        y     = 46 + i * row_h
        rows += f"""
  <circle cx="16" cy="{y+5}" r="5" fill="{color}"/>
  <text x="28" y="{y+10}" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9d1d9">{lang}</text>
  <rect x="110" y="{y}" width="{bw}" height="10" rx="5" fill="{color}" opacity="0.75"/>
  <text x="404" y="{y+10}" font-family="JetBrains Mono,monospace" font-size="10" fill="#8b949e" text-anchor="end">{pct:.0f}%</text>"""

    return f"""<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="CSES Languages">
  <title>CSES Languages</title>
  <defs><clipPath id="rl"><rect width="{w}" height="{h}" rx="12"/></clipPath></defs>
  <rect width="{w}" height="{h}" rx="12" fill="#0d1117" clip-path="url(#rl)"/>
  <rect width="3" height="{h}" fill="#c9373c"/>
  <text x="16" y="22" font-family="JetBrains Mono,monospace" font-size="11" fill="#c9373c" font-weight="700" letter-spacing="2">LANGUAGES USED</text>
  <line x1="16" y1="30" x2="{w-16}" y2="30" stroke="#21262d" stroke-width="1"/>
  {rows}
</svg>"""


# ── MAIN ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user",     required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--out",      default="generated")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    session = make_session()

    print(f"[1/3] Stats públicas de usuario {args.user}...")
    stats = fetch_user_stats(session, args.user)
    print(f"      username={stats['username']}  submissions={stats['submission_count']}  last={stats['last_submission']}")

    print("[2/3] Problemas resueltos por categoría...")
    solved       = fetch_solved_problems(session, args.user)
    total_solved = sum(solved.values())
    print(f"      Total: {total_solved}/{TOTAL_PROBLEMS}")
    for cat, s in solved.items():
        if s > 0:
            print(f"      {cat}: {s}/{CATEGORIES[cat]}")

    print("[3/3] Generando SVGs...")
    files = {
        "cses_overview.svg":   make_overview_svg(stats, total_solved),
        "cses_categories.svg": make_categories_svg(solved),
        "cses_languages.svg":  make_language_svg(stats),
        "cses_solved.svg":     make_overview_svg(stats, total_solved),
    }
    for name, content in files.items():
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"      ✓ {path}")

    print("\nListo.")

if __name__ == "__main__":
    main()
