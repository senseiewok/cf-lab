"""Gallery piece 7, 'The Held Breath': one soap bubble above a flat horizon, a soft shadow below. Uses asciicanvas only.
Run from anywhere: python held_breath.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asciicanvas import Braille, Canvas

W, H = 44, 14           # canvas in character cells
B = Braille(W, 9)       # 88 x 36 pixels
cx, cy, r = 30, 15, 13  # the bubble sits left of centre in cells (x = 15): asymmetry on purpose
B.circle(cx, cy, r)
# the highlight: a short arc inside the upper left, a few pixels of a smaller circle
for t in range(200, 262, 3):
    a = math.radians(t)
    B.set(round(cx + (r - 4) * math.cos(a)), round(cy + (r - 4) * math.sin(a)))
bubble = B.render().split(chr(10))

C = Canvas(W, H)
for y, row in enumerate(bubble):
    for x, ch in enumerate(row):
        if ch != chr(0x2800):
            C.put(x, y, ch)
# the horizon: a long thin line that stops short of the right edge
C.hline(2, 10, 38, "_")
# the shadow: a flat ellipse of shade under the bubble (centre x = 15 cells), lighter towards the edges
C.fill_ramp(3, 11, 25, 1, lambda x, y: 1 - abs(x - 15) / 12.5, ramp=" .:-=")
print(C.render())
