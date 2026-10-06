"""Gallery piece 8, 'The Open Loop': one ring that does not quite close, and a small stone waiting outside the gap.
Braille only. Run from anywhere: python open_loop.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asciicanvas import Braille

B = Braille(36, 10)          # 72 x 40 pixels, 36 columns of text
cx, cy, r = 30, 20, 16       # the ring sits left of centre on purpose
# a stroke two pixels thick reads as a line; one pixel breaks into dots. The gap, upper right, is where the loop
# stops to ask before it closes
B.ring(cx, cy, r, thickness=2, gap=(-64, -24))
# the stone outside the gap: a filled dot on the ring's own radius line, a little further out
a = math.radians(-44)
B.ring(round(cx + (r + 7) * math.cos(a)), round(cy + (r + 7) * math.sin(a)), 2, thickness=3)
print(B.render(trim=True))
