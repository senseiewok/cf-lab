"""Verify a small animated page by pixels and console, with no timing: standard library only, headless Chromium, software renderer, no network.

Why this exists: a model can write an animation that looks right in its head and does nothing, or draws nothing, or ignores the reduced-motion setting.
Free-running animations cannot be judged from screenshots under headless virtual time: measured here, three screenshots of one CSS draw-on animation at the
same virtual-time budget came out blank, blank and fully drawn. So the page under test must have a TEST HOOK: `?t=SECONDS` freezes it at exactly that time.
Every check below uses only frozen states (and the prefers-reduced-motion state), so the result is the same every time.

Two kinds of page:
  svg-draw    an inline SVG path that draws itself on over 1 to 3 seconds and stays drawn
  webgl-mesh  a lit, rotating 3D mesh (WebGL2) drawn from code

The mesh check assumes what the task states: ONE mesh, drawn with one gl.drawElements call per frame from an element array that holds exactly its indices. A page that draws
several meshes in a frame, or over-allocates its index buffer, would be flagged; adapt the check before using it on such a page.

Both pages write a JSON object into an element with id `probe` (the rule of check-webgl.py): svg-draw {"ok":true,"pathLength":N}; webgl-mesh
{"ok":true,"error":0,"triangles":N}. Reads the page as a local file only; any network request is blocked.

Usage: python check-animated-page.py --kind svg-draw|webgl-mesh PAGE.html [--chrome PATH] [--size WxH]
Exit 0 and a last line `N/N checks passed` when every check passes; 1 and one `FAIL reason` line per problem; 2 for a missing page or browser."""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_webgl", HERE / "check-webgl.py")
cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cw)

# Injected into a COPY of the page (never the page itself): records what the page really does, instead of what its probe claims.
# It counts requestAnimationFrame, setInterval and Element.animate calls, counts the animations that are running, and records every
# WebGL2 drawElements call with the length of the element array it was given, then publishes all of it as a data attribute on <html>.
INSTRUMENT = r"""<script>(function(){var d=document.documentElement,st={raf:0,interval:0,animate:0,draws:[],elemLen:null};
function publish(){try{var run=0;if(document.getAnimations){run=document.getAnimations().filter(function(a){return a.playState==='running'}).length}
d.setAttribute('data-instr',JSON.stringify({raf:st.raf,interval:st.interval,animate:st.animate,running:run,drawCount:st.draws.length,draws:st.draws.slice(-3)}))}catch(e){}}
var raf=window.requestAnimationFrame;window.requestAnimationFrame=function(cb){st.raf++;publish();return raf.call(window,cb)};
var si=window.setInterval;window.setInterval=function(){st.interval++;publish();return si.apply(window,arguments)};
if(window.Element&&Element.prototype.animate){var an=Element.prototype.animate;Element.prototype.animate=function(){st.animate++;publish();return an.apply(this,arguments)}}
if(window.WebGL2RenderingContext){var P=WebGL2RenderingContext.prototype,bd=P.bufferData,de=P.drawElements;
P.bufferData=function(t,data){if(t===this.ELEMENT_ARRAY_BUFFER&&data&&typeof data.length==='number'){st.elemLen=data.length}return bd.apply(this,arguments)};
P.drawElements=function(m,c,ty,o){st.draws.push({m:m,c:c,e:st.elemLen});publish();return de.apply(this,arguments)}}
setTimeout(publish,300);setTimeout(publish,800)})();</script>"""


def inject(text):
    for pattern in (r"<head[^>]*>", r"<html[^>]*>"):
        m = re.search(pattern, text, re.I)
        if m:
            return text[:m.end()] + INSTRUMENT + text[m.end():]
    m = re.match(r"\s*<!doctype[^>]*>", text, re.I)
    return (text[:m.end()] + INSTRUMENT + text[m.end():]) if m else INSTRUMENT + text


BUDGET_MS = 1000
SIZE = (400, 300)


class Runner:
    def __init__(self, page, chrome, size):
        self.page, self.chrome, self.size = Path(page).resolve(), chrome, size
        self.problems, self.checks = [], 0
        self._cache = {}

    def check(self, ok, reason):
        self.checks += 1
        if not ok:
            self.problems.append(reason)
        return ok

    def url(self, query=""):
        return self.page.as_uri() + (("?" + query) if query else "")

    def dump(self, query="", reduced=False):
        """(console problems, probe object or None) from the rendered page."""
        key = ("dump", query, reduced)
        if key not in self._cache:
            r = cw.run_chrome(self.chrome, ["--dump-dom"], self.url(query), BUDGET_MS, False, reduced)
            fatal = [re.sub(r"^\[[^\]]*\]\s*", "", ln.strip())[:160] for ln in r.stderr.splitlines() if "CONSOLE" in ln and cw.FATAL_CONSOLE.search(ln)]
            p = cw._Probe("probe")
            p.feed(r.stdout)
            obj = None
            if p.found:
                try:
                    import html
                    obj = json.loads(html.unescape("".join(p.text)).strip())
                    if not isinstance(obj, dict):
                        obj = None
                except ValueError:
                    obj = None
            self._cache[key] = (fatal, obj)
            self._cache[("raw", query, reduced)] = r.stdout
        return self._cache[key]

    def probe_hidden(self, query=""):
        """True when the probe element is still hidden after the page ran (a hidden attribute, or display:none in its style); None if there is no probe tag."""
        self.dump(query)
        raw = self._cache.get(("raw", query, False), "")
        m = re.search(r"<[a-zA-Z][^>]*\bid=[\"']probe[\"'][^>]*>", raw)
        if not m:
            return None
        tag = m.group(0)
        return bool(re.search(r"\bhidden\b", tag)) or bool(re.search(r"display\s*:\s*none", tag))

    def instr(self, query="", reduced=False):
        """What the page really did, from the injected recorder (a dict; empty if the recorder could not report)."""
        key = ("instr", query, reduced)
        if key not in self._cache:
            copy = Path(tempfile.gettempdir()) / f"check-animated-instr-{os.getpid()}-{abs(hash(key))}.html"
            copy.write_text(inject(self.page.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
            r = cw.run_chrome(self.chrome, ["--dump-dom"], copy.as_uri() + (("?" + query) if query else ""), BUDGET_MS, False, reduced)
            m = re.search(r'<html[^>]*\sdata-instr="([^"]*)"', r.stdout)
            data = {}
            if m:
                import html
                try:
                    data = json.loads(html.unescape(m.group(1)))
                except ValueError:
                    data = {}
            try:
                copy.unlink()
            except OSError:
                pass
            self._cache[key] = data
        return self._cache[key]

    def shot(self, query="", reduced=False):
        """The pixel list of a frozen frame."""
        key = ("shot", query, reduced)
        if key not in self._cache:
            out = Path(tempfile.gettempdir()) / f"check-animated-{os.getpid()}-{abs(hash(key))}.png"
            cw.run_chrome(self.chrome, [f"--screenshot={out}", f"--window-size={self.size[0]},{self.size[1]}"], self.url(query), BUDGET_MS, False, reduced)
            try:
                _w, _h, px = cw.decode_png(out.read_bytes())
            except (OSError, ValueError):
                px = []
            finally:
                try:
                    out.unlink()
                except OSError:
                    pass
            self._cache[key] = px
        return self._cache[key]


def frac(pixels):
    return cw.nonblank_fraction(pixels) if pixels else 0.0


def diff_fraction(a, b, tol=8):
    """The share of pixels whose colour differs between two frames by more than tol in any channel."""
    if not a or not b or len(a) != len(b):
        return 1.0
    far = sum(1 for p, q in zip(a, b) if max(abs(p[0] - q[0]), abs(p[1] - q[1]), abs(p[2] - q[2])) > tol)
    return far / len(a)


def interior_luminance(pixels, size):
    """Luminance (0 to 255) of the object's interior pixels: not background, and every 4-neighbour not background (so anti-aliased edges are left out)."""
    if not pixels:
        return []
    w, h = size
    bg = max(set(pixels), key=pixels.count) if len(set(pixels)) < 5000 else pixels[0]
    def far(p):
        return max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) > 8
    out = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            i = y * w + x
            if far(pixels[i]) and far(pixels[i - 1]) and far(pixels[i + 1]) and far(pixels[i - w]) and far(pixels[i + w]):
                r, g, b = pixels[i]
                out.append(0.299 * r + 0.587 * g + 0.114 * b)
    return out


EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//|@import\s+["']?(?:https?:)?//|\bimport\s*\(\s*["']https?:|\bfetch\s*\(|XMLHttpRequest|\bWebSocket\b""", re.I)


def source_checks(r, text):
    scrubbed = re.sub(r"""xmlns(?::\w+)?\s*=\s*["'][^"']*["']""", "", text)
    r.check(not EXTERNAL.search(scrubbed), "the page refers to something outside itself (an external src, href, url(), import, fetch, XMLHttpRequest or WebSocket); it must be one self-contained file")
    r.check(len(text) < 60000, "the page is larger than 60 KB")


def check_svg_draw(r, text):
    source_checks(r, text)
    fatal, probe = r.dump()
    r.check(not fatal, "console: " + "; ".join(fatal[:2]))
    r.check(probe is not None, "no element with id 'probe' holding a JSON object after the page ran")
    if probe is not None:
        r.check(probe.get("ok") is True, "the probe says ok is not true")
        r.check(isinstance(probe.get("pathLength"), (int, float)) and probe["pathLength"] > 0, f"the probe's pathLength is not a positive number: {probe.get('pathLength')!r}")
    r.check(r.probe_hidden() is not False, "the probe element is visible on the page: it must stay hidden (keep the hidden attribute; do not set probe.hidden = false)")
    done = frac(r.shot("t=6"))
    rm = frac(r.shot("t=0", reduced=True))
    r.check(rm >= 0.01, f"with prefers-reduced-motion the path is not drawn (nonblank {rm:.4f}, need at least 0.01): the finished path must show at once")
    start = frac(r.shot("t=0"))
    mid = frac(r.shot("t=1"))
    late = frac(r.shot("t=2.3"))
    r.check(done >= 0.9 * rm and done > 0, f"at t=6 the path is not fully drawn (nonblank {done:.4f}, the reduced-motion finished frame has {rm:.4f})")
    r.check(start <= 0.05 * max(done, 1e-9), f"at t=0 the path is already drawn (nonblank {start:.4f} against {done:.4f} when finished): nothing of it may be visible at the start (at most 5 percent, for the dot a round line cap leaves)")
    r.check(0.15 * done < mid < 0.9 * done, f"at t=1 the drawing is not part way (nonblank {mid:.4f}, finished {done:.4f}): it must be between 15 and 90 percent")
    r.check(late >= 0.9 * done, f"at t=2.3 the path is not finished (nonblank {late:.4f}, finished {done:.4f}): the animation must take about 2 seconds")
    r.check(start < mid <= late + 1e-9, "the drawing does not grow from t=0 through t=1 to t=2.3")
    again = frac(r.shot("t=1"))
    r.check(abs(again - mid) < 1e-9, "the same frozen time gave two different frames: the ?t= hook is not exact")
    # What the page really does, recorded from a copy of it. Frozen frames cannot show whether the free-running mode works at all.
    live, froz, red = r.instr(""), r.instr("t=1"), r.instr("", reduced=True)
    r.check(bool(live) and bool(froz) and bool(red), "the page could not be inspected (the recorder reported nothing)")

    # How many animation frames headless virtual time delivers is not dependable (measured: 1, 2 or 4 depending on flags), so no frame-count threshold is
    # used: the page must START animating (request a frame, start a timer or a Web Animation, or have a CSS animation running), and a frozen or
    # reduced-motion page must stay quiet.
    def starts(d):
        return d.get("raf", 0) >= 1 or d.get("interval", 0) >= 1 or d.get("animate", 0) >= 1 or d.get("running", 0) >= 1

    def quiet(d):
        return d.get("running", 0) == 0 and d.get("raf", 0) <= 1 and d.get("interval", 0) == 0 and d.get("animate", 0) == 0

    r.check(starts(live), "free-running (no ?t=, no reduced motion) nothing starts animating: no animation frame is requested and no animation is running, so the page does not animate on its own")
    r.check(quiet(red), "with prefers-reduced-motion something still animates (an animation running, or timers or repeated frame requests): it must show the finished path with no animation")
    r.check(quiet(froz), "with ?t=1 something still animates: a frozen frame must stay frozen")


def check_webgl_mesh(r, text):
    source_checks(r, text)
    r.check(re.search(r"""getContext\(\s*["']webgl2["']""", text) is not None, "the page does not ask for a webgl2 context (a getContext('webgl2') call)")
    fatal, probe = r.dump("t=0")
    r.check(not fatal, "console: " + "; ".join(fatal[:2]))
    r.check(probe is not None, "no element with id 'probe' holding a JSON object after the page ran")
    if probe is not None:
        r.check(probe.get("ok") is True, "the probe says ok is not true")
        r.check(probe.get("error") == 0, f"the probe's GL error is {probe.get('error')!r}, expected 0")
        r.check(isinstance(probe.get("triangles"), (int, float)) and probe["triangles"] >= 400, f"the mesh has {probe.get('triangles')!r} triangles; it needs at least 400")
    r.check(r.probe_hidden("t=0") is not False, "the probe element is visible on the page: it must stay hidden (keep the hidden attribute; do not set probe.hidden = false)")
    a0, a1, a3 = r.shot("t=0"), r.shot("t=1.5"), r.shot("t=3")
    f0 = frac(a0)
    r.check(f0 >= 0.02, f"at t=0 the mesh covers too little of the canvas (nonblank {f0:.4f}, need at least 0.02)")
    r.check(diff_fraction(a0, a1) >= 0.005, f"the frames at t=0 and t=1.5 are almost the same ({diff_fraction(a0, a1):.4f} of pixels differ, need at least 0.005): the mesh must rotate")
    r.check(diff_fraction(a0, a3) >= 0.005, f"the frames at t=0 and t=3 are almost the same ({diff_fraction(a0, a3):.4f} of pixels differ, need at least 0.005)")
    lum = sorted(interior_luminance(a0, r.size))
    if len(lum) >= 200:
        spread = lum[int(len(lum) * 0.9)] - lum[int(len(lum) * 0.1)]
        bins = len({int(v // 8) for v in lum})
    else:
        spread, bins = 0, 0
    r.check(spread >= 30 and bins >= 8, f"the mesh does not look lit: its interior pixels span {bins} brightness steps and a spread of {spread:.0f} of 255 (need at least 8 steps and 30); a flat colour is not lighting")
    again = r.shot("t=1.5")
    r.check(diff_fraction(a1, again) < 0.001, "the same frozen time gave two different frames: the ?t= hook is not exact")
    rm = r.shot("", reduced=True)
    r.check(frac(rm) >= 0.02, "with prefers-reduced-motion nothing is drawn: it must draw the still t=0 frame")
    r.check(diff_fraction(a0, rm) < 0.005, f"with prefers-reduced-motion the frame is not the still t=0 frame ({diff_fraction(a0, rm):.4f} of pixels differ): no motion is allowed")
    # What the page really draws and how often, recorded from a copy of it: the probe is only the page's own claim.
    froz, red, live = r.instr("t=1.5"), r.instr("", reduced=True), r.instr("")
    r.check(bool(froz) and bool(red) and bool(live), "the page could not be inspected (the recorder reported nothing)")
    draws = froz.get("draws") or []
    last = draws[-1] if draws else None
    r.check(last is not None, "with ?t=1.5 the page made no gl.drawElements call: nothing was drawn by drawElements")
    if last is not None:
        r.check(last.get("m") == 4, f"the draw call does not use gl.TRIANGLES (mode {last.get('m')!r})")
        r.check(last.get("e") is not None and last.get("c") == last.get("e"), f"the draw call draws {last.get('c')!r} indices but the element array holds {last.get('e')!r}: part of the mesh is never drawn (gl.drawElements takes a count of INDICES, three per triangle)")
        if probe is not None and isinstance(probe.get("triangles"), (int, float)) and isinstance(last.get("c"), int):
            r.check(probe["triangles"] * 3 == last["c"], f"the probe claims {probe['triangles']} triangles but the draw call draws {last['c'] // 3}")
    r.check(froz.get("drawCount") == 1, f"with ?t=1.5 the page drew {froz.get('drawCount')!r} frames; it must draw exactly one and stop")
    r.check(red.get("drawCount") == 1, f"with prefers-reduced-motion the page drew {red.get('drawCount')!r} frames; it must draw exactly one still frame and stop")
    # Frame cadence under headless virtual time is not dependable, so ask only for evidence that the loop continues: a second draw, or a second frame request.
    r.check((live.get("drawCount") or 0) >= 2 or (live.get("raf") or 0) >= 2 or (live.get("interval") or 0) >= 1, f"free-running (no ?t=, no reduced motion) the page drew {live.get('drawCount')!r} frame(s) and requested {live.get('raf')!r} animation frame(s): the loop does not continue, so it does not animate on its own")


KINDS = {"svg-draw": check_svg_draw, "webgl-mesh": check_webgl_mesh}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page")
    ap.add_argument("--kind", required=True, choices=sorted(KINDS))
    ap.add_argument("--chrome")
    ap.add_argument("--size", default="400x300")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    page = Path(a.page)
    if not page.is_file():
        print(f"ERROR: no such page: {page}")
        return 2
    chrome = cw.find_chrome(a.chrome)
    if not chrome:
        print("ERROR: no Chromium found; set CHROME_PATH or use --chrome")
        return 2
    try:
        size = tuple(int(x) for x in a.size.lower().split("x"))
        assert len(size) == 2
    except (ValueError, AssertionError):
        print("ERROR: --size must look like 400x300")
        return 2
    text = page.read_text(encoding="utf-8", errors="replace")
    r = Runner(page, chrome, size)
    KINDS[a.kind](r, text)
    for p in r.problems:
        print("FAIL " + p)
    print(f"{r.checks - len(r.problems)}/{r.checks} checks passed")
    return 1 if r.problems else 0


if __name__ == "__main__":
    sys.exit(main())
