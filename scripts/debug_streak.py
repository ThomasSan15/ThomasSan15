#!/usr/bin/env python3
"""
Streak debugger — run this and paste the full output here.
Usage: python debug_streak.py --user ThomasBA
"""
import requests, time, argparse
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0"}
CF_BASE = "https://codeforces.com/api"

def cf_get(method, params, retries=3):
    url = f"{CF_BASE}/{method}"
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            data = r.json()
            if data.get("status") == "OK":
                return data["result"]
            raise RuntimeError(data.get("comment", "error"))
        except Exception as e:
            if attempt == retries - 1: raise
            time.sleep(2 ** attempt)

def fetch_all_subs(handle):
    all_subs, start, batch = [], 1, 10_000
    while True:
        batch_data = cf_get("user.status", {"handle": handle, "from": start, "count": batch})
        if not batch_data: break
        all_subs.extend(batch_data)
        if len(batch_data) < batch: break
        start += batch
        time.sleep(0.3)
    return all_subs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    args = parser.parse_args()

    print(f"Fetching submissions for {args.user}...")
    subs = fetch_all_subs(args.user)
    print(f"Total submissions: {len(subs)}\n")

    # Collect AC days in EVERY timezone variant so we can compare
    tz_variants = {
        "UTC+0  (London)":  timezone(timedelta(hours=0)),
        "UTC+3  (Moscow)":  timezone(timedelta(hours=3)),
        "UTC-5  (Bogota)":  timezone(timedelta(hours=-5)),
    }

    ok_subs = [s for s in subs if s.get("verdict") == "OK"]
    print(f"OK submissions: {len(ok_subs)}\n")

    for tz_name, tz in tz_variants.items():
        ac_days = set()
        for s in ok_subs:
            ts  = s.get("creationTimeSeconds", 0)
            day = datetime.fromtimestamp(ts, tz=tz).date()
            ac_days.add(day)

        today     = datetime.now(tz).date()
        yesterday = today - timedelta(days=1)
        start_day = today if today in ac_days else yesterday

        streak = 0
        d = start_day
        while d in ac_days:
            streak += 1
            d -= timedelta(days=1)

        # max streak
        max_s = running = 0
        prev  = None
        for day in sorted(ac_days):
            if prev and (day - prev) == timedelta(days=1):
                running += 1
            else:
                running = 1
            max_s = max(max_s, running)
            prev  = day

        print(f"[{tz_name}]")
        print(f"  today              : {today}")
        print(f"  streak start day   : {start_day}")
        print(f"  current streak     : {streak} days")
        print(f"  max streak         : {max_s} days")
        print(f"  unique AC days     : {len(ac_days)}")

        # Show the last 70 days to spot gaps
        print(f"  last 70 days with AC:")
        last70 = sorted([d for d in ac_days if d >= today - timedelta(days=70)])
        for i, day in enumerate(last70):
            gap = ""
            if i > 0 and (day - last70[i-1]).days > 1:
                gap = f"  ← GAP of {(day - last70[i-1]).days - 1} day(s)"
            print(f"    {day}{gap}")
        print()

if __name__ == "__main__":
    main()
