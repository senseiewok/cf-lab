#!/usr/bin/env python3
"""mini_seo.py: a small SYNTHETIC site checker used only as the candidate in the review-findings-filter fixtures.

It is cut down from a real script a local model reviewed (2026-10-06) and keeps a few of its real behaviours, including two
that are defects against the spec that script was written to (a 404 page skipped by the content checks, and findings collapsed
by a set), so recorded review findings can be run against it. It is not a SEO tool: do not use it for anything else.

Usage: python mini_seo.py SITE_DIR [--json] [--base-url URL]
Exit 1 when any error-level finding exists, else 0.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ERRORS = {"SEO017", "SEO026"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas, self.imgs, self.links, self.h1, self.ld = [], [], [], 0, []
        self._ld = False
        self._a = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            self.metas.append(a)
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "h1":
            self.h1 += 1
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._ld = True
            self.ld.append("")
        elif tag == "a":
            self._a = [a.get("href", ""), ""]

    def handle_endtag(self, tag):
        if tag == "script":
            self._ld = False
        elif tag == "a" and self._a is not None:
            self.links.append(tuple(self._a))
            self._a = None

    def handle_data(self, data):
        if self._ld:
            self.ld[-1] += data
        elif self._a is not None:
            self._a[1] += data


def url_path(rel):
    p = "/" + rel
    return p[: -len("index.html")] if p.endswith("/index.html") else p


def robots_patterns(root):
    f = root / "robots.txt"
    if not f.is_file():
        return []
    out, applies = [], False
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            applies = value == "*"
        elif key == "disallow" and applies and value:
            out.append(value)
    return out


def audit(root):
    found = set()
    pages = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.html"))
    patterns = robots_patterns(root)
    for rel in pages:
        page = Page()
        page.feed((root / rel).read_text(encoding="utf-8", errors="replace"))
        if rel == "404.html":
            found.add((rel, "SEO017", "404.html is not noindex"))
            continue  # the content checks below are skipped for the 404 page
        path = url_path(rel)
        for pat in patterns:
            hit = re.fullmatch(re.escape(pat[:-1]), path) if pat.endswith("$") else path.startswith(pat)
            if hit:
                found.add(("robots.txt", "SEO026", f"Disallow pattern '{pat}' matches an indexed page"))
        for m in page.metas:
            if m.get("property") == "og:image" and not re.match(r"https?://", m.get("content", "")):
                found.add((rel, "SEO016", f"og:image {m.get('content', '')} is external; not checked"))
        if not page.h1:
            found.add((rel, "SEO030", "page has no h1"))
        for _ in [i for i in page.imgs if "alt" not in i]:
            found.add((rel, "SEO033", "<img> missing alt attribute"))
        for href, text in page.links:
            if not text.strip():
                found.add((rel, "SEO036", f"link has no text (href={href})"))
        for block in page.ld:
            try:
                data = json.loads(block)
            except ValueError:
                found.add((rel, "SEO040", "JSON-LD block is not valid JSON"))
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in list(objs):
                if isinstance(obj, dict):
                    objs.extend(x for x in obj.get("@graph", []) if isinstance(x, dict))
            for obj in objs:
                if "@context" not in obj:
                    found.add((rel, "SEO041", "JSON-LD object missing @context"))
    rows = [{"id": i, "message": m, "page": p, "severity": "error" if i in ERRORS else "warn"} for p, i, m in sorted(found)]
    return pages, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site_dir")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--base-url")
    args = ap.parse_args()
    root = Path(args.site_dir)
    if not root.is_dir():
        print("SITE_DIR is not a directory", file=sys.stderr)
        return 2
    pages, rows = audit(root)
    if args.json:
        print(json.dumps({"findings": rows, "pages": pages, "version": 1}, indent=2, sort_keys=True))
    else:
        for r in rows:
            print(f"{r['page']}: {r['id']} {r['message']}")
    return 1 if any(r["severity"] == "error" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
