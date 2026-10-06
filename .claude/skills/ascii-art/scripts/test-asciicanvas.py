"""Test for asciicanvas.py (a small ASCII/Braille drawing library for agents). Hand-computed expectations on tiny canvases.

Usage: python test-asciicanvas.py [asciicanvas.py]   -> one FAIL line per failing check; prints VERIFIED and exits 0 only when all pass.
"""
import importlib.util
import math
import sys
from pathlib import Path

path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent / "asciicanvas.py"
try:
    spec = importlib.util.spec_from_file_location("asciicanvas_cand", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
except Exception as e:  # noqa: BLE001
    print(f"FAIL import: {type(e).__name__}: {str(e)[:160]}")
    sys.exit(1)

fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"FAIL {name}: got {got!r} want {want!r}")


def attempt(name, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        fails.append(f"FAIL {name}: raised {type(e).__name__}: {str(e)[:100]}")
        return None


Canvas, Braille = getattr(mod, "Canvas", None), getattr(mod, "Braille", None)
if Canvas is None or Braille is None:
    print("FAIL the module must define Canvas and Braille")
    sys.exit(1)

# ---- Canvas basics
check("empty canvas renders empty", attempt("empty", lambda: Canvas(5, 3).render()), "")


def t_put():
    c = Canvas(5, 3)
    c.put(0, 0, "a")
    c.put(4, 2, "b")
    return c.render()


check("put and render keep leading and inner blank lines", attempt("put", t_put), "a\n\n    b")


def t_oob():
    c = Canvas(5, 3)
    for x, y in ((-1, 0), (5, 0), (0, 3), (0, -1)):
        c.put(x, y, "x")
    return c.render()


check("put outside the canvas is ignored", attempt("oob", t_oob), "")


def t_text():
    c = Canvas(6, 3)
    c.text(1, 1, "hey")
    return c.render()


check("text", attempt("text", t_text), "\n hey")


def t_text_clip():
    c = Canvas(6, 2)
    c.text(4, 0, "hello")
    return c.render()


check("text is clipped at the right edge", attempt("textclip", t_text_clip), "    he")


def t_hv():
    c = Canvas(7, 4)
    c.hline(0, 1, 5, "-")
    c.vline(6, 0, 4, "|")
    return c.render()


check("hline length and vline length", attempt("hv", t_hv), "      |\n----- |\n      |\n      |")

# ---- lines: the glyph comes from the whole segment
def line(x0, y0, x1, y1, w=8, h=5):
    c = Canvas(w, h)
    c.line(x0, y0, x1, y1)
    return c.render()


check("line horizontal", attempt("l1", lambda: line(0, 0, 4, 0)), "-----")
check("line vertical", attempt("l2", lambda: line(0, 0, 0, 3)), "|\n|\n|\n|")
check("line diagonal down", attempt("l3", lambda: line(0, 0, 3, 3)), "\\\n \\\n  \\\n   \\")
check("line diagonal up", attempt("l4", lambda: line(0, 3, 3, 0)), "   /\n  /\n /\n/")
check("line reversed endpoints give the same picture", attempt("l5", lambda: line(3, 3, 0, 0)), "\\\n \\\n  \\\n   \\")


def t_shallow():
    c = Canvas(8, 5)
    c.line(0, 0, 6, 3)
    rows = c.render().split("\n")
    cells = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch != " "]
    glyphs = {rows[y][x] for x, y in cells}
    xs = sorted(x for x, _ in cells)
    return (glyphs, xs, (0, 0) in cells, (6, 3) in cells)


check("shallow line: one glyph '-', one cell per column, both ends", attempt("shallow", t_shallow), ({"-"}, [0, 1, 2, 3, 4, 5, 6], True, True))


def t_steep():
    c = Canvas(8, 8)
    c.line(0, 0, 2, 6)
    rows = c.render().split("\n")
    cells = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch != " "]
    return ({rows[y][x] for x, y in cells}, sorted(y for _, y in cells), (0, 0) in cells, (2, 6) in cells)


check("steep line: one glyph '|', one cell per row, both ends", attempt("steep", t_steep), ({"|"}, [0, 1, 2, 3, 4, 5, 6], True, True))

# ---- rect
check("rect ascii", attempt("r1", lambda: (lambda c: (c.rect(0, 0, 5, 3), c.render())[1])(Canvas(5, 3))), "+---+\n|   |\n+---+")
check("rect single", attempt("r2", lambda: (lambda c: (c.rect(0, 0, 5, 3, "single"), c.render())[1])(Canvas(5, 3))), "┌───┐\n│   │\n└───┘")


def t_rect_small():
    try:
        Canvas(5, 5).rect(0, 0, 1, 3)
    except ValueError:
        return "ValueError"
    return "no error"


check("rect with width 1 raises ValueError", attempt("r3", t_rect_small), "ValueError")

# ---- ellipse
def t_ellipse():
    c = Canvas(11, 5)
    c.ellipse(5, 2, 5, 2, "o")
    rows = c.render().split("\n")
    rows += [""] * (5 - len(rows))
    cells = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "o"]
    ok_cells = all(abs(((x - 5) / 5) ** 2 + ((y - 2) / 2) ** 2 - 1) < 0.45 for x, y in cells)
    four = all((x, y) in cells for x, y in ((10, 2), (0, 2), (5, 0), (5, 4)))
    return (ok_cells, four, len(cells) >= 12)


check("ellipse: points near the curve, four extremes, enough points", attempt("e1", t_ellipse), (True, True, True))


def t_ellipse_sym():
    c = Canvas(11, 5)
    c.ellipse(5, 2, 5, 2, "o")
    return c.render() == c.mirror_x().render()


check("a centred ellipse is left-right symmetric", attempt("e2", t_ellipse_sym), True)

# ---- ramp
check("fill_ramp maps 0..1 onto the ramp and clips 1.0 to the last glyph",
      attempt("f1", lambda: (lambda c: (c.fill_ramp(0, 0, 4, 1, lambda x, y: x / 3, ramp=" .:#"), c.render())[1])(Canvas(4, 1))), " .:#")
check("fill_ramp clips values outside 0..1",
      attempt("f2", lambda: (lambda c: (c.fill_ramp(0, 0, 2, 1, lambda x, y: -5 if x == 0 else 9, ramp=" .:#"), c.render())[1])(Canvas(2, 1))), " #")
check("fill_ramp default ramp ends with @",
      attempt("f3", lambda: (lambda c: (c.fill_ramp(0, 0, 1, 1, lambda x, y: 1.0), c.render())[1])(Canvas(1, 1))), "@")

# ---- stamp
check("stamp", attempt("s1", lambda: (lambda c: (c.stamp(1, 0, "ab\ncd"), c.render())[1])(Canvas(4, 2))), " ab\n cd")


def t_stamp_t():
    c = Canvas(3, 1)
    c.text(0, 0, "xxx")
    c.stamp(0, 0, "a b")
    return c.render()


def t_stamp_o():
    c = Canvas(3, 1)
    c.text(0, 0, "xxx")
    c.stamp(0, 0, "a b", transparent=False)
    return c.render()


check("stamp is transparent for spaces by default", attempt("s2", t_stamp_t), "axb")
check("stamp with transparent=False overwrites", attempt("s3", t_stamp_o), "a b")

# ---- mirror
def t_mirror():
    c = Canvas(4, 2)
    c.text(0, 0, "/-(<")
    m = c.mirror_x()
    return (m.render(), c.render(), m is not c)


check("mirror_x flips and swaps / \\ ( ) < > [ ] { } and leaves the original alone", attempt("m1", t_mirror), (">)-\\", "/-(<", True))
check("mirror brackets", attempt("m2", lambda: (lambda c: (c.text(0, 0, "[{"), c.mirror_x().render())[1])(Canvas(2, 1))), "}]")

# ---- Braille
check("empty braille cells are U+2800", attempt("b0", lambda: Braille(2, 1).render()), "⠀⠀")


def bits(cells_w, cells_h, pts):
    b = Braille(cells_w, cells_h)
    for p in pts:
        b.set(*p)
    return [ord(ch) - 0x2800 for ch in b.render().replace("\n", "")]


check("pixel (0,0) is dot 1 = 0x01", attempt("b1", lambda: bits(2, 1, [(0, 0)])), [0x01, 0])
check("pixel (1,0) is 0x08", attempt("b2", lambda: bits(2, 1, [(1, 0)])), [0x08, 0])
check("pixel (0,1) is 0x02 and (0,2) is 0x04", attempt("b3", lambda: bits(1, 1, [(0, 1), (0, 2)])), [0x06])
check("pixel (1,1) is 0x10 and (1,2) is 0x20", attempt("b4", lambda: bits(1, 1, [(1, 1), (1, 2)])), [0x30])
check("pixel (0,3) is 0x40 and (1,3) is 0x80", attempt("b5", lambda: bits(1, 1, [(0, 3), (1, 3)])), [0xC0])
check("pixel (2,0) is the second cell", attempt("b6", lambda: bits(2, 1, [(2, 0)])), [0, 0x01])
check("all eight pixels of a cell give U+28FF", attempt("b7", lambda: bits(1, 1, [(x, y) for x in range(2) for y in range(4)])), [0xFF])
check("pixels outside are ignored", attempt("b8", lambda: bits(1, 1, [(-1, 0), (2, 0), (0, 4), (0, -1)])), [0])
check("size in pixels", attempt("b9", lambda: (Braille(3, 2).width, Braille(3, 2).height)), (6, 8))
check("two rows are joined by a newline", attempt("b10", lambda: Braille(1, 2).render()), "⠀\n⠀")


def t_unset():
    b = Braille(1, 1)
    b.set(0, 0)
    b.set(1, 3)
    b.unset(0, 0)
    return ord(b.render()) - 0x2800


check("unset clears one pixel", attempt("b11", t_unset), 0x80)
check("braille diagonal line", attempt("b12", lambda: (lambda b: (b.line(0, 0, 3, 3), [ord(c) - 0x2800 for c in b.render()])[1])(Braille(2, 1))), [0x11, 0x84])


def t_circle():
    b = Braille(10, 5)  # 20 x 20 pixels
    b.circle(10, 10, 8)
    pts = [(x, y) for y in range(b.height) for x in range(b.width) if (ord(b.render().split("\n")[y // 4][x // 2]) - 0x2800) & _bit(x % 2, y % 4)]
    near = all(abs(math.hypot(x - 10, y - 10) - 8) < 0.9 for x, y in pts)
    four = all(p in pts for p in ((18, 10), (2, 10), (10, 18), (10, 2)))
    return (near, four, len(pts) >= 30)


def _bit(px, py):
    return {(0, 0): 1, (0, 1): 2, (0, 2): 4, (1, 0): 8, (1, 1): 16, (1, 2): 32, (0, 3): 64, (1, 3): 128}[(px, py)]


check("braille circle: pixels on the circle, four extremes, enough pixels", attempt("b13", t_circle), (True, True, True))


# ---- Braille render(trim=True), ring and plot (added 2026-10-05 for gallery pieces 8 and 9)
def lit(b):
    """Set of lit pixel coordinates read back from the rendered cells."""
    rows = b.render().split("\n")
    out = set()
    for cy, row in enumerate(rows):
        for cx, ch in enumerate(row):
            bits = ord(ch) - 0x2800
            for (col, r), bit in {(0, 0): 1, (0, 1): 2, (0, 2): 4, (1, 0): 8, (1, 1): 16, (1, 2): 32, (0, 3): 64, (1, 3): 128}.items():
                if bits & bit:
                    out.add((cx * 2 + col, cy * 4 + r))
    return out


def t_trim():
    b = Braille(3, 3)
    b.set(2, 4)                       # cell (1, 1), dot 1
    return (b.render(trim=True), b.render().count("\n"))


check("render(trim=True) drops blank rows above and below and trailing blank cells, keeps leading U+2800 cells",
      attempt("t1", t_trim), ("⠀⠁", 2))
check("render(trim=True) of an empty canvas is the empty string", attempt("t2", lambda: Braille(2, 2).render(trim=True)), "")


def t_ring():
    b = Braille(4, 2)                 # 8 x 8 pixels
    b.ring(4, 4, 3, thickness=3)      # lit where 0.5 < d <= 3.5
    p = lit(b)
    return ((4, 1) in p, (7, 4) in p, (4, 7) in p, (1, 4) in p, (4, 4) in p, (1, 1) in p)


check("ring: the four extremes are lit, the centre and the far corner are not", attempt("r1", t_ring), (True, True, True, True, False, False))


def t_ring_thin():
    b = Braille(4, 2)
    b.ring(4, 4, 3, thickness=1)      # lit where 2.5 < d <= 3.5
    p = lit(b)
    return ((4, 1) in p, (4, 2) in p, (4, 4) in p)


check("ring with thickness 1 is one pixel wide", attempt("r2", t_ring_thin), (True, False, False))
check("ring with thickness >= r + 1 fills the disc, centre included",
      attempt("r3", lambda: (4, 4) in lit((lambda b: (b.ring(4, 4, 2, thickness=3), b)[1])(Braille(4, 2)))), True)


def t_ring_gap():
    b = Braille(4, 2)
    b.ring(4, 4, 3, thickness=3, gap=(-100, -80))   # the top is at -90 degrees
    p = lit(b)
    return ((4, 1) in p, (7, 4) in p, (4, 7) in p)


check("ring gap leaves the top arc unlit and the rest lit", attempt("r4", t_ring_gap), (False, True, True))


def t_plot_flat():
    b = Braille(3, 1)                 # 6 x 4 pixels
    b.plot(lambda x: 1, 0, 5, thickness=2)
    return [ord(c) - 0x2800 for c in b.render()]


check("plot: a flat line two pixels tall lights rows 1 and 2 of every cell", attempt("p1", t_plot_flat), [0x36, 0x36, 0x36])


def t_plot_steep():
    b = Braille(1, 1)                 # 2 x 4 pixels
    b.plot(lambda x: 3 * x, 0, 1)     # (0, 0) to (1, 3): the columns are joined, so no row is empty
    p = lit(b)
    return ((0, 0) in p, (1, 3) in p, all(any((x, y) in p for x in range(2)) for y in range(4)))


check("plot: a steep stretch has both ends and no hole between them", attempt("p2", t_plot_steep), (True, True, True))
check("plot with thickness 1 on one column is a single pixel", attempt("p3", lambda: lit((lambda b: (b.plot(lambda x: 2, 1, 1), b)[1])(Braille(1, 1)))), {(1, 2)})

print("\n".join(fails[:25]))
print("VERIFIED" if not fails else f"{len(fails)} failing check(s)")
sys.exit(1 if fails else 0)
