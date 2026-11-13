#!/usr/bin/env python3
"""Check whether the real exam facts (content/certifications.yaml `official`) are out of date.

  python scripts/check_facts.py               # list every certification, exit 1 if facts are stale
  python scripts/check_facts.py --warn-only   # never fail (CI prints GitHub warnings instead)
  python scripts/check_facts.py --online      # also open each official page and look for the
                                              # price and the exam minutes in it (a hint only)

Facts are stale when `checked` is more than --max-months months old (default 6). To refresh them:
open the official page, update the facts, and set `checked` to the current month (YYYY-MM).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.content import load_library  # noqa: E402
from app.facts import MAX_AGE_MONTHS, report  # noqa: E402


def page_text(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (study-lab facts check)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(3_000_000).decode("utf-8", "replace")
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
            return r.status, unescape(re.sub(r"<[^>]+>", " ", text))
    except Exception as e:   # network errors are reported, not fatal
        return getattr(e, "code", None), str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-months", type=int, default=MAX_AGE_MONTHS)
    ap.add_argument("--warn-only", action="store_true", help="exit 0 even when facts are stale")
    ap.add_argument("--online", action="store_true", help="fetch the official pages (needs internet)")
    ap.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    lib = load_library(ROOT / "content")
    certs = {c.id: c for c in lib.certifications}
    rows = report(lib.certifications, args.today or date.today(), args.max_months)
    in_ci = os.getenv("GITHUB_ACTIONS") == "true"
    stale = [r for r in rows if r["stale"]]
    for r in rows:
        mark = "STALE" if r["stale"] else "ok"
        print(f"{r['short']:<10} checked {r['checked']} ({r['months']:>2} months)  {mark}")
        if r["stale"] and in_ci:
            print(f"::warning file=content/certifications.yaml::{r['short']} exam facts were checked in "
                  f"{r['checked']} ({r['months']} months ago). Check {r['url']} and update `checked`.")
        if args.online:
            o = certs[r["id"]].official
            status, text = page_text(o.url)
            hints = []
            price = re.search(r"\d+(?:[.,]\d+)?", o.cost)
            if price:
                hints.append(f"price {price.group()} {'found' if price.group() in text else 'NOT found'}")
            hours = o.minutes / 60   # pages often say "2 hours" instead of "120 minutes"
            found = re.search(rf"\b{o.minutes}\b", text) or (hours == int(hours) and re.search(
                rf"\b{int(hours)}\s*(hours?|hrs?)\b|\b{['', 'one', 'two', 'three', 'four'][int(hours)] if hours < 5 else '-'}\s+hours?\b",
                text, re.I))
            hints.append(f"{o.minutes} minutes {'found' if found else 'NOT found'}")
            print(f"           page: HTTP {status} · " + " · ".join(hints) + ("" if status == 200 else f" · {text[:80]}"))
    if args.online:
        print("\n'NOT found' is only a hint: many pages load prices with JavaScript or show them per country.")
    if stale:
        print(f"\n{len(stale)} certification(s) have facts older than {args.max_months} months: "
              + ", ".join(r["short"] for r in stale))
        print("Open each official page, update content/certifications.yaml and set `checked` to this month.")
        return 0 if args.warn_only else 1
    print(f"\nAll exam facts were checked in the last {args.max_months} months.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
