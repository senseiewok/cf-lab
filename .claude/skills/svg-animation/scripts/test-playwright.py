"""Optional: check the two SVG examples with real Playwright for Python (the claims test-examples.py makes, through a different tool).

Usage: <playwright-venv-python> test-playwright.py [--channel msedge|chrome|chromium] [--allow-skip]
Needs Playwright for Python and a browser; see the playwright-browser-testing skill (setup-browser-testing.py, opt-in, outside every repo).
Without Playwright it prints a SKIP line and exits 2, or exits 0 with --allow-skip. No network: every http, https, ws and ftp request is aborted and reported.
The PNG pixel helpers come from ../../webgl-threejs-graphics/scripts/check-webgl.py (the same dependency test-examples.py has).

For examples/line-draw.html and examples/draw-on.html, once normally and once with prefers-reduced-motion emulated (page.emulate_media), it asserts:
  no console error and no uncaught page error; no request and no WebSocket other than the page itself (file: or data: only);
  normally document.getAnimations() reports at least one running animation, with reduced motion it reports none;
  the SVG has an accessible name: an element with role img, tag svg, and a non-empty name as Playwright computes it (aria-labelledby or aria-label);
  a screenshot taken after the animations finished is not blank (the drawing is visible in both modes).
Negative control: small bad pages written to a temporary folder (console error, page error, remote request, animation that ignores reduced motion,
no drawing, no accessible name) are run through the same checks, and each must FAIL for its own reason; a good control page must pass.
Prints VERIFIED and exits 0 only when the examples pass and every bad page fails; otherwise one FAIL line per problem and exit 1."""
import argparse
import importlib.util
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent / "examples"
CHECK_WEBGL = HERE.parent.parent / "webgl-threejs-graphics" / "scripts" / "check-webgl.py"
SKIP_MESSAGE = "SKIP: Playwright is not installed (see playwright-browser-testing)"
ALLOWED_SCHEMES = {"file", "data"}
BLOCKED = re.compile(r"^(https?|wss?|ftp)://", re.I)
MIN_NONBLANK = 0.003   # the same minimum test-examples.py uses for the thin line
RUNNING = "document.getAnimations().filter(a => a.playState === 'running').length"
TOTAL = "document.getAnimations().length"
SETTLE = ("Promise.race([Promise.all(document.getAnimations().map(a => a.finished.catch(() => null))), "
          "new Promise(r => setTimeout(r, 3000))])")
NAMED_SVGS = "els => els.filter(e => e.tagName.toLowerCase() === 'svg').length"


def load_helpers():
    spec = importlib.util.spec_from_file_location("check_webgl", CHECK_WEBGL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Recorder:
    def __init__(self, page):
        self.requests, self.console, self.page_errors, self.sockets = [], [], [], []
        page.on("request", lambda r: self.requests.append(r.url))
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on("websocket", lambda w: self.sockets.append(w.url))


def observe(browser, url, reduced, PlaywrightError):
    """Load one page in a fresh context and return what a person or a script could see; never raises for a page problem."""
    obs = {"load_error": None, "running": None, "total": None, "named_svgs": None, "shot": None}
    ctx = browser.new_context(viewport={"width": 400, "height": 300}, accept_downloads=False, service_workers="block")
    try:
        ctx.route(BLOCKED, lambda route: route.abort())
        page = ctx.new_page()
        rec = Recorder(page)
        page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
        try:
            page.goto(url, wait_until="load", timeout=20000)
            # Measure first: the examples draw for about 2 seconds and then the animation is finished, not running.
            obs["running"] = page.evaluate(RUNNING)
            obs["total"] = page.evaluate(TOTAL)
            named = page.get_by_role("img", name=re.compile(r"\S"))
            obs["named_svgs"] = named.evaluate_all(NAMED_SVGS)
            page.evaluate(SETTLE)
            obs["shot"] = page.screenshot()
        except PlaywrightError as exc:
            obs["load_error"] = " ".join(str(exc).split())[:200]
        obs.update(requests=rec.requests, console=rec.console, page_errors=rec.page_errors, sockets=rec.sockets)
    finally:
        ctx.close()
    return obs


def judge(label, normal, reduced, cw):
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
        errors = [t for ty, t in obs.get("console", []) if ty == "error"]
        check(not errors, f"{mode}: console error: {errors[:2]}")
        check(not obs.get("page_errors"), f"{mode}: uncaught page error: {obs.get('page_errors', [])[:2]}")
        check((obs["named_svgs"] or 0) >= 1, f"{mode}: no svg with role img and an accessible name was found")
        if obs["shot"]:
            frac = cw.nonblank_fraction(cw.decode_png(obs["shot"])[2])
            check(frac >= MIN_NONBLANK, f"{mode}: the finished drawing looks blank ({frac:.4f} of pixels differ from the background, need {MIN_NONBLANK})")
        else:
            check(False, f"{mode}: no screenshot was taken")
    check((normal["running"] or 0) >= 1, f"normal motion: document.getAnimations() reports {normal['running']!r} running animations, expected at least 1")
    check(reduced["total"] == 0, f"reduced motion: the page animates under reduced motion (document.getAnimations() reports {reduced['total']!r} animations, expected 0)")
    return problems, count[0]


TEMPLATE = """<!doctype html><html lang="en"><meta charset="utf-8"><title>control page</title>
<style>
html, body { margin: 0; background: #fff; }
svg { display: block; }
path { fill: none; stroke: @STROKE@; stroke-width: 6; stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 2s linear @ITER@ forwards; }
@keyframes draw { to { stroke-dashoffset: 0; } }
@media (prefers-reduced-motion: reduce) { @REDUCED@ }
</style>
<svg width="400" height="300" viewBox="0 0 400 300" @NAME@><path pathLength="1" d="M20 150 C 80 20, 140 280, 200 150 S 320 20, 380 150"/></svg>
<script>@EXTRA@</script>"""

# name -> (substitutions, text a failure message must contain; None for the good control, which must pass)
CONTROLS = {
    "control-good": ({}, None),
    "bad-console-error": ({"@EXTRA@": "console.error('control: deliberate console error');"}, "console error"),
    "bad-page-error": ({"@EXTRA@": "setTimeout(function () { throw new Error('control: deliberate page error'); }, 50);"}, "uncaught page error"),
    "bad-remote-request": ({"@EXTRA@": "fetch('http://example.invalid/data.json').catch(function () {});"}, "a request left the page"),
    "bad-ignores-reduced-motion": ({"@REDUCED@": "", "@ITER@": "infinite"}, "animates under reduced motion"),
    "bad-nothing-drawn": ({"@STROKE@": "none"}, "looks blank"),
    "bad-no-accessible-name": ({"@NAME@": ""}, "no svg with role img and an accessible name"),
}


def make_control(substitutions):
    text = TEMPLATE
    defaults = (("@STROKE@", "#c0392b"), ("@ITER@", "1"), ("@REDUCED@", "path { animation: none; stroke-dashoffset: 0; }"),
                ("@NAME@", 'role="img" aria-label="A wave drawn on"'), ("@EXTRA@", ""))
    for key, default in defaults:
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
    if not CHECK_WEBGL.is_file():
        print("FAIL the pixel helpers are missing:", CHECK_WEBGL)
        return 1
    cw = load_helpers()
    failures = []

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, **({} if a.channel == "chromium" else {"channel": a.channel}))
        except PlaywrightError as exc:
            print("ERROR: could not start the browser:", " ".join(str(exc).split())[:200])
            return 2
        try:
            def run(label, path):
                url = Path(path).resolve().as_uri()
                return judge(label, observe(browser, url, False, PlaywrightError), observe(browser, url, True, PlaywrightError), cw)

            for name in ("line-draw.html", "draw-on.html"):
                problems, n = run(name, EXAMPLES / name)
                failures += problems
                if not problems:
                    print(f"ok   {name}: {n} checks passed")
            for name, (subs, expect) in CONTROLS.items():
                path = Path(tmp) / f"{name}.html"
                path.write_text(make_control(subs), encoding="utf-8")
                problems, n = run(name, path)
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
