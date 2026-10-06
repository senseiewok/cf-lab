"""Gallery piece 9, 'The Measured Line': a curve drawn solid only where there are measured points, and plain dots where
there are none. Echoes the lab's CFTR model page, where a stretch no structure places is a dotted connector, not a
shape. Braille only. Run from anywhere: python measured_line.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asciicanvas import Braille

B = Braille(40, 9)           # 80 x 36 pixels, 40 columns of text


def curve(x):                # one arch across the field, its crest right of centre
    return 30 - 24 * math.sin((x - 2) / 76 * math.pi) ** 1.6


# the measured stretches: a stroke three pixels tall, so it reads as a tube and not as a row of dots
B.plot(curve, 2, 30, thickness=3)
B.plot(curve, 58, 77, thickness=3)
# the unmeasured stretch: single dots on a straight line between the two ends, below the crest the curve would have
(xa, ya), (xb, yb) = (30, round(curve(30))), (58, round(curve(58)))
for i in range(1, 9):
    t = i / 9
    B.set(round(xa + (xb - xa) * t), round(ya + (yb - ya) * t) + 1)
print(B.render(trim=True))
