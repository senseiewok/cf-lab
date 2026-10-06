"""Gallery piece 11, 'The Threaded Gap': a long gentle double helix with one small gap in one strand, and a thin thread
curving up toward it from the lower right. An emblem of the work of understanding, not a diagram of a gene or a
repair; the README text beside it says so. Braille only. Run from anywhere: python threaded_gap.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asciicanvas import Braille

B = Braille(60, 8)                       # 120 x 32 pixels, 60 columns of text
X0, X1 = 2, 117                          # the helix runs almost the whole width
CY, A, PERIOD = 13, 9, 76                # centre line, half-height, one full twist every 76 pixels
K = 2 * math.pi / PERIOD
GAP = (52, 63)                           # the gap, in pixels: the lower strand, just left of the middle


def strand(x, sign):
    return CY + sign * A * math.sin(K * (x - X0))


def is_front(x, sign):
    """A helix seen from the side: the strand whose depth cosine is positive is nearer the viewer."""
    return sign * math.cos(K * (x - X0)) > 0


def near_crossing(x):
    return abs(math.sin(K * (x - X0))) < 0.22


for sign in (1, -1):
    for x in range(X0, X1):
        if sign == -1 and GAP[0] <= x <= GAP[1]:
            continue                                            # the gap
        if is_front(x, sign):
            B.plot(lambda t: strand(t, sign), x, x + 1, thickness=2)   # the near strand: a stroke
        elif not near_crossing(x) and x % 2 == 0:
            B.set(x, round(strand(x, sign)))                    # the far strand: single dots, hidden at crossings

# the thread: single dots on a quadratic curve from below the field, bending left into the gap's right end, then
# two dots along the missing path: the part already worked in
gx, gy = GAP[1] + 1, round(strand(GAP[1] + 1, -1))
p0, p1, p2 = (96, 31), (80, 31), (gx, gy)
for i in range(0, 81, 3):
    t = i / 80
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
    B.set(round(x), round(y))
for x in (GAP[1] - 2, GAP[1] - 5):
    B.set(x, round(strand(x, -1)))
print(B.render(trim=True))
