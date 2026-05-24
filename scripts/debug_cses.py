#!/usr/bin/env python3
"""
Script de diagnóstico — corre esto UNA VEZ en GitHub Actions
para ver el HTML real que devuelve CSES y encontrar las clases correctas.
"""

import requests
from bs4 import BeautifulSoup
import os

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def main():
    cookie_val = os.getenv("CSES_SESSION", "").strip()
    if cookie_val.startswith("PHPSESSID="):
        cookie_val = cookie_val.split("=", 1)[1]

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.set("PHPSESSID", cookie_val, domain="cses.fi")

    url = "https://cses.fi/problemset/user/416103/"
    resp = session.get(url, timeout=15)
    print(f"HTTP: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. Verificar login
    logged_in = bool(soup.find("a", href="/logout"))
    print(f"Autenticado: {logged_in}")

    # 2. Mostrar todos los <h2> que encuentra
    print("\n=== H2 tags encontrados ===")
    for h2 in soup.find_all("h2"):
        print(f"  h2: '{h2.text.strip()}'")

    # 3. Mostrar todas las clases únicas que tienen los <a> tags
    print("\n=== Clases únicas en <a> tags ===")
    all_classes = set()
    for a in soup.find_all("a"):
        for c in a.get("class", []):
            all_classes.add(c)
    for c in sorted(all_classes):
        print(f"  .{c}")

    # 4. Contar <a> con cada clase
    print("\n=== Conteo de <a> por clase ===")
    from collections import Counter
    class_counter = Counter()
    for a in soup.find_all("a"):
        for c in a.get("class", []):
            class_counter[c] += 1
    for cls, count in class_counter.most_common():
        print(f"  .{cls}: {count} elementos")

    # 5. Mostrar los primeros 5 <a> que tengan cualquier clase
    print("\n=== Primeros 10 <a> con clase ===")
    shown = 0
    for a in soup.find_all("a"):
        if a.get("class") and shown < 10:
            print(f"  classes={a.get('class')}  text='{a.text.strip()[:40]}'  href='{a.get('href','')[:50]}'")
            shown += 1

    # 6. Mostrar fragmento del HTML alrededor de la primera sección
    print("\n=== HTML de las primeras 3000 chars de <main> o <body> ===")
    main_tag = soup.find("main") or soup.find("body")
    if main_tag:
        print(str(main_tag)[:3000])

if __name__ == "__main__":
    main()
