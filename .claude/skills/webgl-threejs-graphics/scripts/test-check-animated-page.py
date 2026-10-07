"""Test for check-animated-page.py: a verifier that has never failed proves nothing.

Each reference page must pass. Each bad stub is the reference with ONE change (made here by text replacement, so the stubs cannot drift from the
references) and must fail with the reason that change causes. Needs a Chromium (the same one check-webgl.py finds); no network.
Usage: python test-check-animated-page.py     One FAIL line per failing check; VERIFIED and exit 0 when all pass."""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check-animated-page.py"
MESH_REF = HERE.parent / "examples" / "lit-torus.html"
SVG_REF = HERE.parent.parent / "svg-animation" / "examples" / "draw-on.html"
fails = []


def check(name, ok, detail=""):
    if not ok:
        fails.append(name)
        print(f"FAIL {name}" + (f"  ({detail})" if detail else ""))


def run(kind, page):
    p = subprocess.run([sys.executable, str(CHECKER), "--kind", kind, str(page)], capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout, p.stderr


SVG_STUBS = {
    "static: the path is fully drawn from the start and nothing animates": ([("animation: draw 2s linear forwards;", ""), ("stroke-dashoffset: var(--len);", "stroke-dashoffset: 0;")], "already drawn"),
    "blank: the stroke is invisible": ([("stroke: #c0392b;", "stroke: none;")], "not drawn"),
    "ignores reduced motion": ([("@media (prefers-reduced-motion: reduce) { path { animation: none; stroke-dashoffset: 0; } }", "")], "reduced-motion"),
    "stops half way": ([("@keyframes draw { to { stroke-dashoffset: 0; } }", "@keyframes draw { to { stroke-dashoffset: calc(var(--len) / 2); } }")], "not fully drawn"),
    "takes 3 seconds, not 2": ([("animation: draw 2s linear forwards;", "animation: draw 3s linear forwards;")], "not finished"),
    "already 15 percent drawn at the start": ([("@keyframes draw { to { stroke-dashoffset: 0; } }", "@keyframes draw { from { stroke-dashoffset: calc(var(--len) * 0.85); } to { stroke-dashoffset: 0; } }")], "already drawn"),
    "the probe is a visible div, not a hidden pre": ([("<pre id=\"probe\" hidden></pre>", "<div id=\"probe\"></div>")], "probe element is visible"),
    "too slow (10 seconds)": ([("animation: draw 2s linear forwards;", "animation: draw 10s linear forwards;")], "not finished"),
    "a console error": ([("<pre id=\"probe\" hidden></pre>", "<pre id=\"probe\" hidden></pre><script>undefinedThing();</script>")], "console:"),
    "an external stylesheet": ([("<style>", "<link rel=\"stylesheet\" href=\"https://example.com/x.css\"><style>")], "outside itself"),
    "no probe element": ([("document.getElementById('probe').textContent", "void 0 && document.getElementById('probe').textContent")], "probe"),
    "animates only under the test hook, never on its own": ([("animation: draw 2s linear forwards; }", " }"), ("if (t !== null) { p.style.animationPlayState = 'paused';", "if (t !== null) { p.style.animation = 'draw 2s linear forwards'; p.style.animationPlayState = 'paused';")], "nothing starts animating"),
    "leaves the probe visible on the page": ([("<pre id=\"probe\" hidden></pre>", "<pre id=\"probe\"></pre>")], "probe element is visible"),
    "keeps a timer running under reduced motion": ([("<pre id=\"probe\" hidden></pre>", "<pre id=\"probe\" hidden></pre><script>setInterval(function () {}, 50);</script>")], "still animates"),
}
MESH_STUBS = {
    "unlit: a flat colour": ([("outColor = vec4(base * (0.15 + 0.85 * d), 1.0);", "outColor = vec4(base, 1.0);")], "does not look lit"),
    "does not rotate": ([("return t * 2 * Math.PI / 6;", "return 0.0;")], "almost the same"),
    "ignores reduced motion": ([("matchMedia('(prefers-reduced-motion: reduce)').matches", "false")], "reduced-motion"),
    "draws nothing": ([("gl.drawElements(", "0 && gl.drawElements(")], "too little"),
    "a shader error": ([("outColor = vec4(base * (0.15 + 0.85 * d), 1.0);", "outColor = ;")], "console:"),
    "too few triangles": ([("const U = 48, V = 24", "const U = 6, V = 4")], "triangles"),
    "an external script": ([("<script>", "<script src=\"https://example.com/x.js\"></script><script>")], "outside itself"),
    "WebGL 1 instead of 2": ([("getContext('webgl2')", "getContext('webgl')")], "webgl2"),
    "a GL error": ([("gl.enable(gl.DEPTH_TEST);", "gl.enable(0); gl.enable(gl.DEPTH_TEST);")], "GL error"),
    "the probe is a visible div, not a hidden pre": ([("<pre id=\"probe\" hidden></pre>", "<div id=\"probe\"></div>")], "probe element is visible"),
    "unhides the probe after drawing (every first worker page did)": ([("<pre id=\"probe\" hidden></pre>", "<pre id=\"probe\" hidden></pre><script>addEventListener('load', function () { document.getElementById('probe').hidden = false; });</script>")], "probe element is visible"),
    "draws a third of the indices (a count of triangles where indices are wanted)": ([("gl.drawElements(gl.TRIANGLES, idx.length, gl.UNSIGNED_SHORT, 0);", "gl.drawElements(gl.TRIANGLES, idx.length / 3, gl.UNSIGNED_SHORT, 0);")], "part of the mesh is never drawn"),
    "the loop stops after the first frame": ([("draw((now - t0) / 1000); requestAnimationFrame(loop);", "draw((now - t0) / 1000);")], "loop does not continue"),
    "the test hook keeps drawing": ([("else if (hook !== null) draw(parseFloat(hook));", "else if (hook !== null) { draw(parseFloat(hook)); setInterval(() => draw(parseFloat(hook)), 50); }")], "exactly one and stop"),
    "reduced motion keeps drawing": ([("if (reduced) draw(0);", "if (reduced) { draw(0); setInterval(() => draw(0), 50); }")], "exactly one still frame"),
    "the probe claims a triangle count it does not draw": ([("triangles: idx.length / 3 }", "triangles: idx.length }")], "probe claims"),
}


def derive(src, edits):
    out = src
    for old, new in edits:
        if old not in out:
            return None
        out = out.replace(old, new, 1)
    return out


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    for kind, ref, stubs in (("svg-draw", SVG_REF, SVG_STUBS), ("webgl-mesh", MESH_REF, MESH_STUBS)):
        if not ref.exists():
            check(f"{kind}: the reference page exists", False, str(ref))
            continue
        code, out, err = run(kind, ref)
        last = out.strip().splitlines()[-1] if out.strip() else ""
        check(f"{kind}: the reference page passes (exit 0 and N/N checks passed)", code == 0 and last.endswith("checks passed") and last.split("/")[0] == last.split("/")[1].split(" ")[0], f"exit={code} out={out[:300]!r} err={err[:120]!r}")
        code2, out2, _ = run(kind, ref)
        check(f"{kind}: running the reference twice gives identical output", out == out2, f"{out[:120]!r} vs {out2[:120]!r}")
        src = ref.read_text(encoding="utf-8")
        for name, (edits, reason) in stubs.items():
            stub_src = derive(src, edits)
            if stub_src is None:
                check(f"{kind} stub '{name}': the edit applies to the reference", False, "the text to replace is not in the reference")
                continue
            page = tmp / f"{kind}-{abs(hash(name))}.html"
            page.write_text(stub_src, encoding="utf-8")
            code, out, err = run(kind, page)
            fail_lines = [l for l in out.splitlines() if l.startswith("FAIL")]
            check(f"{kind} stub '{name}': fails (exit 1)", code == 1 and fail_lines, f"exit={code} out={out[:200]!r}")
            check(f"{kind} stub '{name}': a FAIL line says why (mentions '{reason}')", any(reason in l for l in fail_lines), "; ".join(l[:90] for l in fail_lines[:3]))
    # the rest of the interface
    code, out, err = run("svg-draw", tmp / "no-such-page.html")
    check("a missing page exits 2 with an ERROR line", code == 2 and out.startswith("ERROR"), f"exit={code} {out[:100]!r}")
    p = subprocess.run([sys.executable, str(CHECKER), "--kind", "nonsense", str(SVG_REF)], capture_output=True, text=True, timeout=60)
    check("an unknown --kind exits 2", p.returncode == 2, f"exit={p.returncode}")

print("VERIFIED" if not fails else f"{len(fails)} failing check(s)")
sys.exit(1 if fails else 0)
