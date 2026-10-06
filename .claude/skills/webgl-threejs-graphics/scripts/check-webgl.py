"""Verify a local WebGL page in headless Chromium: no Playwright, no network, a software renderer.

Why this exists: a model can write WebGL that looks right and draws nothing. This renders the page for real and checks three things a script can
decide: the page reports success in a probe element, the page threw no uncaught error and no GL error reached the console, and a screenshot is not blank.

The page under test writes a JSON object into an element with id `probe` (default) when it has drawn, for example
    document.getElementById('probe').textContent = JSON.stringify({ ok: true, error: gl.getError() });
`--expect KEY=VALUE` checks fields of that object (booleans compare as true/false). The renderer is SwiftShader (a software GL): headless Chromium has
no WebGL2 with `--disable-gpu` alone (measured here), it needs `--use-angle=swiftshader --enable-unsafe-swiftshader`. All network access is blocked
unless `--allow-network` is given (a page that must not call out is then proved by the block). The page is a local file you wrote or reviewed.

Usage: python check-webgl.py PAGE.html [--probe ID] [--expect K=V ...] [--budget-ms 3000] [--screenshot [--min-nonblank 0.01] [--size WxH] [--out PNG]]
                                       [--reduced-motion] [--allow-network] [--chrome PATH]
Exit 0 and a first line PASS when every check passes; 1 and FAIL with reasons; 2 for a missing page or browser. Standard library only."""
import argparse
import glob
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

FATAL_CONSOLE = re.compile(r"Uncaught|ReferenceError|TypeError|SyntaxError|WebGL: (INVALID|CONTEXT_LOST)|GL_INVALID|Shader (compile|link)|Failed to compile|CONTEXT_LOST", re.I)
BASE_FLAGS = ["--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-first-run",
              "--disable-extensions", "--disable-component-update", "--disable-background-networking", "--disable-sync", "--enable-logging=stderr", "--v=0"]


def find_chrome(explicit=None):
    cands = [explicit, os.environ.get("CHROME_PATH")]
    home = Path.home()
    for pattern in (home / "AppData/Local/ms-playwright/chromium-*/chrome-win64/chrome.exe", home / ".cache/ms-playwright/chromium-*/chrome-linux/chrome",
                    home / "Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"):
        cands += sorted(glob.glob(str(pattern)), reverse=True)
    cands += [shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome", "chrome")]
    for c in cands:
        if c and Path(c).is_file():
            return str(c)
    return None


# ---- a minimal PNG reader: 8-bit RGB or RGBA, not interlaced (what headless Chromium writes) ----------------------------------
def decode_png(data):
    """Return (width, height, [(r, g, b), ...]). Raises ValueError for anything this reader does not support."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, ihdr, idat = 8, None, b""
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if ihdr is None:
        raise ValueError("no IHDR")
    width, height, depth, ctype, _comp, _filt, interlace = ihdr
    if depth != 8 or ctype not in (2, 6) or interlace != 0:
        raise ValueError(f"unsupported PNG (depth {depth}, colour type {ctype}, interlace {interlace})")
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(idat)
    stride = width * bpp
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG data has the wrong length")
    prev = bytearray(stride)
    pixels = []
    for y in range(height):
        f = raw[y * (stride + 1)]
        row = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                row[i] = (row[i] + a) & 255
            elif f == 2:
                row[i] = (row[i] + b) & 255
            elif f == 3:
                row[i] = (row[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
            elif f != 0:
                raise ValueError(f"bad PNG filter {f}")
        pixels += [(row[i], row[i + 1], row[i + 2]) for i in range(0, stride, bpp)]
        prev = row
    return width, height, pixels


def nonblank_fraction(pixels, tolerance=8):
    """The share of pixels that differ from the most common colour by more than `tolerance` in any channel."""
    if not pixels:
        return 0.0
    bg = Counter(pixels).most_common(1)[0][0]
    far = sum(1 for p in pixels if max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) > tolerance)
    return far / len(pixels)


class _Probe(HTMLParser):
    def __init__(self, probe_id):
        super().__init__(convert_charrefs=True)
        self.probe_id, self.depth, self.text, self.found = probe_id, 0, [], False

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.depth += 1
        elif dict(attrs).get("id") == self.probe_id:
            self.found, self.depth = True, 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


def run_chrome(chrome, extra, url, budget_ms, network, reduced_motion=False):
    # No --user-data-dir: measured on Chromium 153 under Windows, a fresh --user-data-dir makes headless Chromium hang forever, and every other flag here is fine.
    flags = BASE_FLAGS + [f"--virtual-time-budget={budget_ms}"]
    if not network:
        flags.append("--host-resolver-rules=MAP * ~NOTFOUND")
    if reduced_motion:
        flags.append("--force-prefers-reduced-motion")
    return subprocess.run([chrome, *flags, *extra, url], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=budget_ms / 1000 + 60)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a local WebGL page in headless Chromium.")
    ap.add_argument("page")
    ap.add_argument("--probe", default="probe")
    ap.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--budget-ms", type=int, default=3000)
    ap.add_argument("--screenshot", action="store_true")
    ap.add_argument("--min-nonblank", type=float, default=0.01)
    ap.add_argument("--size", default="400x300")
    ap.add_argument("--out")
    ap.add_argument("--query", default="", help="a query string for the page URL, for pages that have test hooks (for example --query lose)")
    ap.add_argument("--reduced-motion", action="store_true", help="run the page with prefers-reduced-motion: reduce switched on")
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--chrome")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    page = Path(a.page)
    if not page.is_file():
        print(f"ERROR: no such page: {page}")
        return 2
    chrome = find_chrome(a.chrome)
    if not chrome:
        print("ERROR: no Chromium found; set CHROME_PATH or use --chrome")
        return 2
    url = page.resolve().as_uri() + (("?" + a.query.lstrip("?")) if a.query else "")
    problems, summary = [], {}

    r = run_chrome(chrome, ["--dump-dom"], url, a.budget_ms, a.allow_network, a.reduced_motion)
    fatal = [ln.strip() for ln in r.stderr.splitlines() if "CONSOLE" in ln and FATAL_CONSOLE.search(ln)]
    for ln in fatal[:5]:
        problems.append("console: " + re.sub(r"^\[[^\]]*\]\s*", "", ln)[:200])
    p = _Probe(a.probe)
    p.feed(r.stdout)
    if not p.found:
        problems.append(f"no element with id '{a.probe}' in the rendered page")
    else:
        text = html.unescape("".join(p.text)).strip()
        try:
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError
        except ValueError:
            obj = None
            problems.append(f"the probe did not hold a JSON object: {text[:80]!r}")
        if obj is not None:
            summary["probe"] = obj
            if obj.get("ok") is not True:
                problems.append("the probe says ok is not true")
            for item in a.expect:
                k, _, want = item.partition("=")
                got = obj.get(k)
                got_s = str(got).lower() if isinstance(got, bool) else str(got)
                if k not in obj or got_s != want.lower() if isinstance(got, bool) else (k not in obj or got_s != want):
                    problems.append(f"expected {k}={want}, the probe has {got!r}")

    if a.screenshot:
        try:
            w, h = (int(x) for x in a.size.lower().split("x"))
        except ValueError:
            print("ERROR: --size must look like 400x300")
            return 2
        shot = Path(a.out) if a.out else Path(tempfile.gettempdir()) / f"check-webgl-{os.getpid()}.png"
        run_chrome(chrome, [f"--screenshot={shot}", f"--window-size={w},{h}"], url, a.budget_ms, a.allow_network, a.reduced_motion)
        try:
            sw, sh, pixels = decode_png(shot.read_bytes())
            frac = nonblank_fraction(pixels)
            summary["nonblank"] = round(frac, 4)
            summary["screenshot"] = f"{sw}x{sh}"
            if frac < a.min_nonblank:
                problems.append(f"the render looks blank: {frac:.4f} of pixels differ from the background (minimum {a.min_nonblank})")
        except (OSError, ValueError, zlib.error) as e:
            problems.append(f"could not read the screenshot: {e}")
        finally:
            if not a.out:
                shot.unlink(missing_ok=True)

    print("FAIL" if problems else "PASS")
    for pr in problems:
        print("  - " + pr)
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
