"""Test for check-webgl.py: a headless-Chromium verifier for a local WebGL page (no network, no Playwright).
Usage: python test-check-webgl.py [SCRIPT]      One FAIL line per failing check; prints VERIFIED and exits 0 when all pass.
Needs a Chromium build (CHROME_PATH or the Playwright download); without one it prints SKIPPED and exits 0 so a stripped-down machine stays green."""
import importlib.util
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

cand = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "check-webgl.py"
try:
    spec = importlib.util.spec_from_file_location("cand_cw", cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
except Exception as e:  # noqa: BLE001
    print(f"FAIL import: {type(e).__name__}: {str(e)[:160]}")
    sys.exit(1)

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(f"FAIL {name}: {detail}")


# ---- PNG decoding: all five filter types, RGB and RGBA ---------------------------------------------------------------
def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def encode_png(rows, ctype, filters):
    """rows: list of bytes objects (pixels as bytes); ctype 2=RGB 6=RGBA; filters: filter type per row."""
    bpp = 3 if ctype == 2 else 4
    width = len(rows[0]) // bpp
    raw, prev = b"", bytes(len(rows[0]))
    for row, f in zip(rows, filters):
        out = bytearray()
        for i, x in enumerate(row):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            pred = [0, a, b, (a + b) // 2, paeth(a, b, c)][f]
            out.append((x - pred) & 0xFF)
        raw += bytes([f]) + bytes(out)
        prev = row
    ihdr = struct.pack(">IIBBBBB", width, len(rows), 8, ctype, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


rows_rgb = [bytes([(x * 37 + y * 11 + k) % 256 for x in range(5) for k in range(3)]) for y in range(5)]
rows_rgba = [bytes([(x * 29 + y * 7 + k * 3) % 256 for x in range(4) for k in range(4)]) for y in range(4)]
for f in range(5):
    w, h, px = mod.decode_png(encode_png(rows_rgb, 2, [f] * 5))
    check(f"decode RGB filter {f}", (w, h) == (5, 5) and px == [tuple(r[i:i + 3]) for r in rows_rgb for i in range(0, len(r), 3)], f"{w}x{h}")
    w, h, px = mod.decode_png(encode_png(rows_rgba, 6, [f] * 4))
    check(f"decode RGBA filter {f}", (w, h) == (4, 4) and px == [tuple(r[i:i + 3]) for r in rows_rgba for i in range(0, len(r), 4)], f"{w}x{h}")
# a Paeth tie: left 0, up 15, up-left 5 -> the predictor must pick "up" (the non-strict comparison); a strict one picks "up-left"
tie_rows = [bytes([5, 5, 5, 15, 15, 15]), bytes([0, 0, 0, 40, 40, 40])]
check("decode paeth tie", mod.decode_png(encode_png(tie_rows, 2, [0, 4]))[2] == [(5, 5, 5), (15, 15, 15), (0, 0, 0), (40, 40, 40)])
mixed = encode_png(rows_rgb, 2, [0, 1, 2, 3, 4])
check("decode mixed filters", mod.decode_png(mixed)[2] == [tuple(r[i:i + 3]) for r in rows_rgb for i in range(0, len(r), 3)])
for bad in (b"", b"not a png", b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 16, 2, 0, 0, 0)), b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 1))):
    try:
        mod.decode_png(bad)
        check("decode refuses a bad or unsupported png", False, repr(bad[:12]))
    except ValueError:
        pass

# ---- pixel statistics ------------------------------------------------------------------------------------------------------
flat = [(10, 10, 10)] * 100
check("blank image has no non-background fraction", mod.nonblank_fraction(flat) == 0.0)
half = [(10, 10, 10)] * 50 + [(255, 0, 0)] * 50
check("half image fraction", abs(mod.nonblank_fraction(half) - 0.5) < 1e-9, str(mod.nonblank_fraction(half)))
check("tiny differences are ignored", mod.nonblank_fraction([(10, 10, 10)] * 50 + [(12, 11, 10)] * 50) == 0.0)
check("empty list is zero", mod.nonblank_fraction([]) == 0.0)

# ---- the browser checks ---------------------------------------------------------------------------------------------------
chrome = mod.find_chrome()
if not chrome:
    print("SKIPPED: no Chromium found (set CHROME_PATH); the decoder checks above ran")
    if fails:
        print("\n".join(fails))
        sys.exit(1)
    sys.exit(0)

GOOD = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>t</title></head><body style="margin:0;background:#000">
<canvas id="c" width="300" height="200"></canvas><pre id="probe">pending</pre><script>
var gl=document.getElementById('c').getContext('webgl2',{preserveDrawingBuffer:true});
function sh(t,s){var x=gl.createShader(t);gl.shaderSource(x,s);gl.compileShader(x);return x}
var p=gl.createProgram();gl.attachShader(p,sh(gl.VERTEX_SHADER,'#version 300 es\\nin vec2 q;void main(){gl_Position=vec4(q,0.,1.);}'));
gl.attachShader(p,sh(gl.FRAGMENT_SHADER,'#version 300 es\\nprecision mediump float;out vec4 o;void main(){o=vec4(1.,.5,0.,1.);}'));gl.linkProgram(p);gl.useProgram(p);
var b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,0,1]),gl.STATIC_DRAW);
var l=gl.getAttribLocation(p,'q');gl.enableVertexAttribArray(l);gl.vertexAttribPointer(l,2,gl.FLOAT,false,0,0);
gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.drawArrays(gl.TRIANGLES,0,3);
var px=new Uint8Array(4);gl.readPixels(150,60,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);
document.getElementById('probe').textContent=JSON.stringify({ok:true,r:px[0],g:px[1],error:gl.getError()});
</script></body></html>"""
NOTOK = GOOD.replace("ok:true", "ok:false")
THROWS = GOOD.replace("var gl=", "throw new Error('boom from the page');var gl=")
BLANK = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>t</title></head><body style="margin:0;background:#000"><pre id="probe">{"ok":true}</pre></body></html>'
NOPROBE = GOOD.replace('id="probe"', 'id="other"')
NETWORK = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>t</title></head><body style="margin:0;background:#000"><pre id="probe">pending</pre><script>
fetch('https://example.com/', {mode: 'no-cors'}).then(function(){document.getElementById('probe').textContent='{"ok":false,"net":"reached"}'}).catch(function(){document.getElementById('probe').textContent='{"ok":true,"net":"blocked"}'});
</script></body></html>"""


def run(html, *args):
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "page.html"
        page.write_text(html, encoding="utf-8")
        r = subprocess.run([sys.executable, str(cand), str(page), *args], capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout + r.stderr


rc, out = run(GOOD, "--expect", "ok=true", "--expect", "r=255", "--expect", "g=128", "--screenshot", "--min-nonblank", "0.2")
check("a working WebGL page passes", rc == 0 and "PASS" in out, f"{rc} {out[-300:]}")
rc, out = run(GOOD, "--expect", "r=0")
check("a wrong expected value fails", rc == 1 and "r" in out, f"{rc} {out[-300:]}")
rc, out = run(NOTOK)
check("a page reporting ok false fails", rc == 1, f"{rc} {out[-300:]}")
rc, out = run(THROWS)
check("an uncaught page error fails and is named", rc == 1 and "boom from the page" in out, f"{rc} {out[-300:]}")
rc, out = run(BLANK, "--screenshot", "--min-nonblank", "0.05")
check("a blank render fails the screenshot check", rc == 1 and "blank" in out.lower(), f"{rc} {out[-300:]}")
rc, out = run(NOPROBE)
check("a missing probe element fails and says so", rc == 1 and "no element with id" in out, f"{rc} {out[-300:]}")
rc, out = run(NETWORK, "--expect", "net=blocked")
check("the network is blocked by default", rc == 0, f"{rc} {out[-300:]}")
MOTION = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>t</title></head><body style="margin:0;background:#000"><pre id="probe">pending</pre><script>
document.getElementById('probe').textContent=JSON.stringify({ok:true,reduce:window.matchMedia('(prefers-reduced-motion: reduce)').matches});
</script></body></html>"""
rc, out = run(MOTION, "--expect", "reduce=false")
check("reduced motion is off by default", rc == 0, f"{rc} {out[-200:]}")
rc, out = run(MOTION, "--reduced-motion", "--expect", "reduce=true")
check("--reduced-motion turns the preference on", rc == 0, f"{rc} {out[-200:]}")

# the skill's own example: it draws, it recovers from a lost context, and it needs preventDefault to do so (a measured claim, not a quoted one)
EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "triangle.html"
if EXAMPLE.is_file():
    rc, out = subprocess.run([sys.executable, str(cand), str(EXAMPLE), "--expect", "ok=true", "--expect", "recovered=false", "--screenshot", "--min-nonblank", "0.03"], capture_output=True, text=True).returncode, ""
    check("the example draws", rc == 0, str(rc))
    rc = subprocess.run([sys.executable, str(cand), str(EXAMPLE), "--query", "lose", "--expect", "ok=true", "--expect", "recovered=true"], capture_output=True, text=True).returncode
    check("the example recovers from a lost context", rc == 0, str(rc))
    with tempfile.TemporaryDirectory() as td:
        broken = Path(td) / "broken.html"
        broken.write_text(EXAMPLE.read_text(encoding="utf-8").replace("e.preventDefault();", ""), encoding="utf-8")
        rc = subprocess.run([sys.executable, str(cand), str(broken), "--query", "lose", "--expect", "recovered=true"], capture_output=True, text=True).returncode
        check("without preventDefault the context is not restored", rc == 1, str(rc))
else:
    check("the example exists", False, str(EXAMPLE))
rc, out = subprocess.run([sys.executable, str(cand), str(Path(tempfile.gettempdir()) / "no-such-page-xyz.html")], capture_output=True, text=True).returncode, ""
check("a missing page exits 2", rc == 2, str(rc))

if fails:
    print("\n".join(fails))
    sys.exit(1)
print("VERIFIED")
