"""Test the svg-animation skill's example in a real browser, using the verifier that lives in the webgl-threejs-graphics skill.
Usage: python test-examples.py     One FAIL line per failing check; prints VERIFIED (or SKIPPED without a Chromium) and exits 0 when all pass."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent / "examples" / "line-draw.html"
VERIFIER = HERE.parent.parent / "webgl-threejs-graphics" / "scripts" / "check-webgl.py"
fails = []


def run(*args):
    r = subprocess.run([sys.executable, str(VERIFIER), str(EXAMPLE), *args], capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout + r.stderr


if not VERIFIER.is_file():
    print("FAIL: the verifier is missing:", VERIFIER)
    sys.exit(1)
rc, out = run("--expect", "reduce=false")
if "no Chromium found" in out:
    print("SKIPPED: no Chromium found (set CHROME_PATH)")
    sys.exit(0)
if rc != 0:
    fails.append(f"FAIL the example does not load normally: {out[-300:]}")
if '"animations": 1' not in out and '"animations": 2' not in out:
    fails.append(f"FAIL with motion allowed the line should be animating: {out[-300:]}")
if '"dasharray": "1px"' not in out and '"dasharray": "1"' not in out:
    fails.append(f"FAIL with motion allowed the dash pattern should be set: {out[-300:]}")
rc, out = run("--reduced-motion", "--expect", "reduce=true", "--expect", "animations=0", "--expect", "dasharray=none")
if rc != 0:
    fails.append(f"FAIL with reduced motion the line must be drawn at once, with no animation: {out[-300:]}")
rc, out = run("--reduced-motion", "--expect", "hasName=true", "--screenshot", "--min-nonblank", "0.003")
if rc != 0:
    fails.append(f"FAIL the finished drawing should be visible and named: {out[-300:]}")
if fails:
    print("\n".join(fails))
    sys.exit(1)
print("VERIFIED")
