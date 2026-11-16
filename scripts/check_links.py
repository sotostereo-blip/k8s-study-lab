#!/usr/bin/env python3
"""Check every docs link in content/ (questions, lab tasks, glossary, exam facts): it must answer
200 after redirects. Reports broken links and links that redirect to another page (moved docs).

  python scripts/check_links.py              # all links
  python scripts/check_links.py --only kcna  # links in files under content/kcna/
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"https?://[^\s\"'`<>)\]},]+")
HEADERS = {"User-Agent": "Mozilla/5.0 (link check; k8s-study-lab)", "Accept": "text/html,*/*"}


DOC_KEYS = {"docs", "url", "source", "links"}   # where content keeps links to read (not lab scripts)


def _walk(node, under_doc_key: bool, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, k in DOC_KEYS, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, under_doc_key, out)
    elif isinstance(node, str) and under_doc_key:
        whole = node.strip()
        out.extend([whole] if re.fullmatch(r"https?://\S+", whole) else URL.findall(node))


def collect(only: str | None) -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for f in sorted((ROOT / "content").rglob("*.yaml")):
        rel = f.relative_to(ROOT / "content")
        if only and rel.parts[0] != only:
            continue
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            continue    # the content validator reports it
        urls: list[str] = []
        _walk(data, False, urls)
        for u in urls:
            found[u.rstrip(".:;")].add(str(rel))
    return found


def check(url: str) -> tuple[str, int | str, str]:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return url, r.status, r.geturl()
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 404, 405, 429, 501):
                continue    # some sites answer HEAD badly: try GET
            return url, e.code, url
        except Exception as e:   # noqa: BLE001  (DNS, TLS, timeout)
            if method == "HEAD":
                continue
            return url, type(e).__name__, url
    return url, "error", url


def moved(url: str, final: str) -> bool:
    norm = lambda u: re.sub(r"[#?].*$", "", u).rstrip("/").replace("http://", "https://")  # noqa: E731
    return norm(url) != norm(final)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="a folder under content/, e.g. kcna")
    a = ap.parse_args()
    links = collect(a.only)
    print(f"checking {len(links)} links…", flush=True)
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(check, sorted(links)))
    broken = [(u, s) for u, s, _ in results if s != 200]
    redirected = [(u, f) for u, s, f in results if s == 200 and moved(u, f)]
    for u, s in broken:
        print(f"BROKEN {s}  {u}\n         in {', '.join(sorted(links[u]))}")
    for u, f in redirected:
        print(f"MOVED   {u}\n     ->  {f}")
    print(f"{len(links)} links: {len(broken)} broken, {len(redirected)} redirected")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
