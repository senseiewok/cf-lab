"""Optional: check the two WebGL examples with real Playwright for Python (the same claims check-webgl.py makes, through a different tool).

Usage: <playwright-venv-python> test-playwright.py [--channel msedge|chrome|chromium] [--allow-skip]
Needs Playwright for Python and a browser; see the playwright-browser-testing skill (setup-browser-testing.py, opt-in, outside every repo).
Without Playwright it prints a SKIP line and exits 2, or exits 0 with --allow-skip. No network: every http, https, ws and ftp request is aborted and reported.

For examples/triangle.html and examples/lit-torus.html, each in a normal run and a prefers-reduced-motion run (page.emulate_media), it asserts:
  the probe element holds a JSON object with ok true and a GL error of 0 (plus what each page really reports: triangles, paused);
  no console error, no GL error line and no uncaught page error; no request and no WebSocket other than the page itself (file: or data: only);
  a screenshot that is not blank (pixel check from check-webgl.py); normally the page animates (requestAnimationFrame is called, two screenshots differ);
  with reduced motion it does not (no requestAnimationFrame call, two screenshots identical, a still frame is drawn).
Negative control: small bad pages written to a temporary folder (console error, page error, remote request, animation that ignores reduced motion,
blank canvas, probe not ok) are run through the same checks, and each must FAIL for its own reason; a good control page must pass.
Prints VERIFIED and exits 0 only when the examples pass and every bad page fails; otherwise one FAIL line per problem and exit 1."""
import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
SKIP_MESSAGE = "SKIP: Playwright is not installed (see playwright-browser-testing)"
# Measured: headless Chromium has no WebGL2 with --disable-gpu alone; and no --user-data-dir (a fresh one hangs it).
LAUNCH_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
ALLOWED_SCHEMES = {"file", "data"}
RAF_COUNTER = "(function(){var r=window.requestAnimationFrame;window.__rafCount=0;window.requestAnimationFrame=function(cb){window.__rafCount++;return r.call(window,cb)}})();"
PROBE_READY = "() => { const p = document.getElementById('probe'); return !!p && /^\\s*[\\[{]/.test(p.textContent); }"
BLOCKED = re.compile(r"^(https?|wss?|ftp)://", re.I)


def load_helpers():
    spec = importlib.util.spec_from_file_location("check_webgl", HERE / "check-webgl.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def diff_fraction(p, q, tol):
    if len(p) != len(q):
        return 1.0
    return sum(1 for a, b in zip(p, q) if max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) > tol) / max(len(p), 1)


class Recorder:
    def __init__(self, page):
        self.requests, self.console, self.page_errors, self.sockets = [], [], [], []
        page.on("request", lambda r: self.requests.append(r.url))
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on("websocket", lambda w: self.sockets.append(w.url))


def observe(browser, url, reduced, PlaywrightError):
    """Load one page in a fresh context and return what a person or a script could see; never raises for a page problem."""
    obs = {"load_error": None, "probe": None, "shots": [], "raf": None}
    ctx = browser.new_context(viewport={"width": 400, "height": 300}, accept_downloads=False, service_workers="block")
    try:
        ctx.route(BLOCKED, lambda route: route.abort())
        page = ctx.new_page()
        rec = Recorder(page)
        page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        page.add_init_script(RAF_COUNTER)
        try:
            page.goto(url, wait_until="load", timeout=20000)
            try:
                page.wait_for_function(PROBE_READY, timeout=8000)
            except PlaywrightError:
                pass  # no JSON probe: reported by the check below
            obs["probe"] = page.evaluate("(document.getElementById('probe') || {}).textContent ?? null")
            page.wait_for_timeout(300)
            obs["shots"].append(page.screenshot())
            page.wait_for_timeout(700)
            obs["shots"].append(page.screenshot())
            obs["raf"] = page.evaluate("window.__rafCount")
        except PlaywrightError as exc:
            obs["load_error"] = " ".join(str(exc).split())[:200]
        obs.update(requests=rec.requests, console=rec.console, page_errors=rec.page_errors, sockets=rec.sockets)
    finally:
        ctx.close()
    return obs


def judge(label, normal, reduced, spec, cw):
    """Return (problems, number of checks). Every problem line starts with the page label."""
    problems, count = [], [0]

    def check(ok, msg):
        count[0] += 1
        if not ok:
            problems.append(f"{label}: {msg}")

    for mode, obs in (("normal motion", normal), ("reduced motion", reduced)):
        check(obs["load_error"] is None, f"{mode}: the page did not load or could not be read: {obs['load_error']}")
        outside = [u for u in obs.get("requests", []) if urlparse(u).scheme not in ALLOWED_SCHEMES] + obs.get("sockets", [])
        check(not outside, f"{mode}: a request left the page: {outside[:3]}")
        errors = [t for ty, t in obs.get("console", []) if ty == "error" or cw.FATAL_CONSOLE.search(t)]
        check(not errors, f"{mode}: console error: {errors[:2]}")
        check(not obs.get("page_errors"), f"{mode}: uncaught page error: {obs.get('page_errors', [])[:2]}")
        probe = None
        try:
            probe = json.loads(obs["probe"]) if obs["probe"] else None
        except ValueError:
            probe = None
        check(isinstance(probe, dict), f"{mode}: the probe element does not hold a JSON object ({str(obs['probe'])[:60]!r})")
        if isinstance(probe, dict):
            check(probe.get("ok") is True, f"{mode}: the probe says ok is not true ({probe})")
            check(probe.get("error") == 0, f"{mode}: the probe GL error is {probe.get('error')!r}, expected 0")
            for msg in spec["probe"](probe, mode == "reduced motion"):
                check(False, f"{mode}: {msg}")
        pixels = [cw.decode_png(s)[2] for s in obs["shots"]] if len(obs["shots"]) == 2 else []
        obs["pixels"] = pixels
        if pixels:
            frac = cw.nonblank_fraction(pixels[0])
            check(frac >= 0.01, f"{mode}: the screenshot looks blank ({frac:.4f} of pixels differ from the background, need 0.01)")

    if normal["pixels"] and spec["moves"]:
        d = diff_fraction(normal["pixels"][0], normal["pixels"][1], 8)
        check((normal["raf"] or 0) >= 2, f"normal motion: the page does not animate (requestAnimationFrame called {normal['raf']!r} times)")
        check(d >= 0.002, f"normal motion: two screenshots 0.7 s apart are almost the same ({d:.4f} of pixels differ, need 0.002)")
    if reduced["pixels"]:
        d = diff_fraction(reduced["pixels"][0], reduced["pixels"][1], 2)
        check(reduced["raf"] == 0, f"reduced motion: the page animates under reduced motion (requestAnimationFrame called {reduced['raf']!r} times, expected 0)")
        check(d == 0.0, f"reduced motion: the page animates under reduced motion (two screenshots 0.7 s apart differ in {d:.4f} of pixels)")
    return problems, count[0]


def probe_triangle(probe, reduced):
    out = []
    if probe.get("paused") is not reduced:
        out.append(f"paused is {probe.get('paused')!r}, expected {reduced}")
    if probe.get("recovered") is not False:
        out.append(f"recovered is {probe.get('recovered')!r}, expected false (no context loss was requested)")
    return out


def probe_torus(probe, reduced):
    t = probe.get("triangles")
    return [] if isinstance(t, (int, float)) and t >= 400 else [f"triangles is {t!r}, expected at least 400"]


GOOD = [("triangle.html", {"probe": probe_triangle, "moves": True}), ("lit-torus.html", {"probe": probe_torus, "moves": True})]
GENERIC = {"probe": lambda probe, reduced: [], "moves": True}

TEMPLATE = """<!doctype html><html lang="en"><meta charset="utf-8"><title>control page</title>
<style>html,body{margin:0;background:#000}canvas{display:block}</style>
<canvas id="c" width="200" height="150"></canvas><pre id="probe" hidden></pre>
<script>
const g = document.getElementById('c').getContext('2d');
const BLANK = @BLANK@, IGNORE_REDUCED = @IGNORE@;
function draw(t) { g.fillStyle = '#000'; g.fillRect(0, 0, 200, 150); if (!BLANK) { g.fillStyle = '#f80'; g.fillRect(20 + ((t / 10) % 100), 30, 80, 80); } }
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
draw(0);
if (IGNORE_REDUCED || !reduced) { (function loop(now) { draw(now); requestAnimationFrame(loop); })(0); }
@EXTRA@
document.getElementById('probe').textContent = JSON.stringify({ ok: @OK@, error: 0 });
</script>"""

# name -> (substitutions, text a failure message must contain; None for the good control, which must pass)
CONTROLS = {
    "control-good": ({}, None),
    "bad-console-error": ({"@EXTRA@": "console.error('control: deliberate console error');"}, "console error"),
    "bad-page-error": ({"@EXTRA@": "setTimeout(function () { throw new Error('control: deliberate page error'); }, 50);"}, "uncaught page error"),
    "bad-remote-request": ({"@EXTRA@": "fetch('http://example.invalid/data.json').catch(function () {});"}, "a request left the page"),
    "bad-ignores-reduced-motion": ({"@IGNORE@": "true"}, "animates under reduced motion"),
    "bad-blank": ({"@BLANK@": "true"}, "looks blank"),
    "bad-probe-not-ok": ({"@OK@": "false"}, "the probe says ok is not true"),
}


def make_control(substitutions):
    text = TEMPLATE
    for key, default in (("@BLANK@", "false"), ("@IGNORE@", "false"), ("@EXTRA@", ""), ("@OK@", "true")):
        text = text.replace(key, substitutions.get(key, default))
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--channel", default="msedge", choices=["msedge", "chrome", "chromium"],
                    help="msedge or chrome use the installed browser; chromium uses Playwright's own download (default msedge)")
    ap.add_argument("--allow-skip", action="store_true", help="exit 0 instead of 2 when Playwright is not installed")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(SKIP_MESSAGE)
        return 0 if a.allow_skip else 2
    cw = load_helpers()
    failures = []

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, args=LAUNCH_ARGS, **({} if a.channel == "chromium" else {"channel": a.channel}))
        except PlaywrightError as exc:
            print("ERROR: could not start the browser:", " ".join(str(exc).split())[:200])
            return 2
        try:
            def run(label, path, spec):
                url = Path(path).resolve().as_uri()
                return judge(label, observe(browser, url, False, PlaywrightError), observe(browser, url, True, PlaywrightError), spec, cw)

            for name, spec in GOOD:
                problems, n = run(name, EXAMPLES / name, spec)
                failures += problems
                if not problems:
                    print(f"ok   {name}: {n} checks passed")
            for name, (subs, expect) in CONTROLS.items():
                path = Path(tmp) / f"{name}.html"
                path.write_text(make_control(subs), encoding="utf-8")
                problems, n = run(name, path, GENERIC)
                if expect is None:
                    failures += problems
                    if not problems:
                        print(f"ok   {name}: passes, as it must ({n} checks)")
                elif not problems:
                    failures.append(f"{name}: the check PASSED a bad page; a check that cannot fail proves nothing")
                elif not any(expect in p for p in problems):
                    failures.append(f"{name}: failed, but not for the expected reason ({expect!r}): {problems[:2]}")
                else:
                    print(f"ok   {name}: failed as it must ({expect})")
        finally:
            browser.close()

    for f in failures:
        print("FAIL " + f)
    if failures:
        return 1
    print("VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
