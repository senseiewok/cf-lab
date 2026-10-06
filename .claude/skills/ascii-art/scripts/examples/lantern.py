"""Gallery piece 10, 'The Lantern': one hanging lamp, lit, in an empty field. ASCII line style, placed cell by cell.
Run from anywhere: python lantern.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asciicanvas import Canvas

C = Canvas(40, 14)
x = 25                        # the lamp hangs right of centre on purpose
C.put(x, 0, ".")              # the hook
C.vline(x, 1, 2, "|")         # a short chain
C.text(x - 2, 3, "_.|._")     # the cap
C.put(x - 3, 4, "/")
C.put(x + 3, 4, "\\")
for y in range(5, 10):        # the glass, five rows tall
    C.put(x - 4, y, "|")
    C.put(x + 4, y, "|")
C.put(x - 3, 10, "\\")
C.hline(x - 2, 10, 5, "_")
C.put(x + 3, 10, "/")
C.text(x - 1, 11, "'-'")      # the base
C.put(x, 6, ".")              # the flame: a point, a small body, a wick
C.text(x - 1, 7, "(:)")
C.put(x, 8, "'")
print(C.render())
