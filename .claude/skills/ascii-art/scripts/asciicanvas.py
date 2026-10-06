"""A small drawing library for composing ASCII art in code instead of typing it freehand.

Why: language models read ASCII art far better than they draw it (see SKILL.md, section 6), so compose on a grid with
exact primitives, render, look at the result, and adjust. Coordinates: x is the column (0 = left), y is the row
(0 = top). Everything outside the grid is ignored. Canvas draws with characters; Braille draws pixels, 2 wide and 4 tall
per character cell, for smooth curves.
"""

import math


class Canvas:
    """A grid of single characters that can be drawn onto and rendered to text."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[' ' for _ in range(width)] for _ in range(height)]

    def put(self, x, y, ch):
        """Set one cell at (x, y) to character ch. Out-of-bounds is ignored."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = ch

    def text(self, x, y, s):
        """Write string s left to right starting at (x, y), clipped at the right edge."""
        for i, c in enumerate(s):
            cx = x + i
            if 0 <= cx < self.width and 0 <= y < self.height:
                self.grid[y][cx] = c

    def hline(self, x, y, length, ch="-"):
        """Draw a horizontal line of given length starting at (x, y)."""
        for i in range(length):
            cx = x + i
            if 0 <= cx < self.width and 0 <= y < self.height:
                self.grid[y][cx] = ch

    def vline(self, x, y, length, ch="|"):
        """Draw a vertical line of given length starting at (x, y)."""
        for i in range(length):
            cy = y + i
            if 0 <= x < self.width and 0 <= cy < self.height:
                self.grid[cy][x] = ch

    def line(self, x0, y0, x1, y1, ch=None):
        """Draw a straight line, both ends included. The glyph is chosen once from the whole slope unless ch is given."""
        dx = x1 - x0
        dy = y1 - y0

        if ch is None:
            adx = abs(dx)
            ady = abs(dy)
            if dy == 0 or adx >= 2 * ady:
                ch = '-'
            elif dx == 0 or ady >= 2 * adx:
                ch = '|'
            elif dx * dy > 0:
                ch = '\\'
            else:
                ch = '/'

        # one cell per column (shallow) or per row (steep), stepping evenly along the longer axis
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            self.put(x0, y0, ch)
            return

        for i in range(steps + 1):
            t = i / steps
            ix = round(x0 + dx * t)
            iy = round(y0 + dy * t)
            self.put(ix, iy, ch)

    def rect(self, x, y, w, h, style="ascii"):
        """Draw a rectangle outline at (x, y) with width w and height h."""
        if w < 2 or h < 2:
            raise ValueError("Rectangle dimensions must be at least 2")

        if style == "ascii":
            tl, tr = '+', '+'
            bl, br = '+', '+'
            hch, vch = '-', '|'
        elif style == "single":
            tl, tr = '\u250c', '\u2510'
            bl, br = '\u2514', '\u2518'
            hch, vch = '\u2500', '\u2502'
        else:
            raise ValueError(f"Unknown style: {style}")

        # Top edge
        for i in range(w):
            cx = x + i
            if 0 <= cx < self.width and 0 <= y < self.height:
                if i == 0:
                    self.grid[y][cx] = tl
                elif i == w - 1:
                    self.grid[y][cx] = tr
                else:
                    self.grid[y][cx] = hch

        # Bottom edge
        by = y + h - 1
        for i in range(w):
            cx = x + i
            if 0 <= cx < self.width and 0 <= by < self.height:
                if i == 0:
                    self.grid[by][cx] = bl
                elif i == w - 1:
                    self.grid[by][cx] = br
                else:
                    self.grid[by][cx] = hch

        # Left and right edges (excluding corners)
        for j in range(1, h - 1):
            cy = y + j
            if 0 <= cy < self.height:
                if 0 <= x < self.width:
                    self.grid[cy][x] = vch
                rx = x + w - 1
                if 0 <= rx < self.width:
                    self.grid[cy][rx] = vch

    def ellipse(self, cx, cy, rx, ry, ch="*"):
        """Draw an ellipse outline. Note: for a round circle use ry = rx / 2."""
        steps = 720
        for i in range(steps):
            t = 2 * math.pi * i / steps
            px = round(cx + rx * math.cos(t))
            py = round(cy + ry * math.sin(t))
            self.put(px, py, ch)

    def fill_ramp(self, x, y, w, h, fn, ramp=" .:-=+*#%@"):
        """Fill a region with characters based on a function value mapped to a ramp."""
        for j in range(h):
            cy = y + j
            if not (0 <= cy < self.height):
                continue
            for i in range(w):
                cx = x + i
                if not (0 <= cx < self.width):
                    continue
                v = fn(cx, cy)
                v = max(0.0, min(1.0, v))
                idx = min(len(ramp) - 1, int(v * len(ramp)))
                self.grid[cy][cx] = ramp[idx]

    def stamp(self, x, y, art, transparent=True):
        """Paste a multi-line string with top-left at (x, y)."""
        lines = art.split('\n')
        for j, line in enumerate(lines):
            cy = y + j
            if not (0 <= cy < self.height):
                continue
            for i, c in enumerate(line):
                cx = x + i
                if not (0 <= cx < self.width):
                    continue
                if transparent and c == ' ':
                    continue
                self.grid[cy][cx] = c

    def mirror_x(self):
        """Return a new Canvas flipped left to right with mirrored characters."""
        swap = {
            '/': '\\', '\\': '/',
            '(': ')', ')': '(',
            '<': '>', '>': '<',
            '[': ']', ']': '[',
            '{': '}', '}': '{'
        }
        new_canvas = Canvas(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                ch = self.grid[y][x]
                mirrored_ch = swap.get(ch, ch)
                new_x = self.width - 1 - x
                new_canvas.grid[y][new_x] = mirrored_ch
        return new_canvas

    def render(self):
        """Render the canvas to a string with trailing spaces and empty lines removed."""
        lines = []
        for row in self.grid:
            line = ''.join(row).rstrip()
            lines.append(line)

        # Remove trailing empty lines
        while lines and lines[-1] == '':
            lines.pop()

        return '\n'.join(lines)


# Braille dot bits by (column, row) inside one character cell: U+2800 plus the sum of the lit dots.
_BIT = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40, (1, 3): 0x80}


class Braille:
    """Pixel art in Unicode Braille characters: each cell is 2 pixels wide and 4 tall.

    Braille cells render at the same width as the other characters in a monospaced font on most platforms, but some
    fonts draw them faintly or with a different width; look at the result where it will be shown.
    """

    def __init__(self, cells_w, cells_h):
        self.cells_w = cells_w
        self.cells_h = cells_h
        self.width = 2 * cells_w
        self.height = 4 * cells_h
        self._lit = [[False] * self.width for _ in range(self.height)]

    def set(self, px, py):
        """Turn a pixel on. Out-of-bounds is ignored."""
        if 0 <= px < self.width and 0 <= py < self.height:
            self._lit[py][px] = True

    def unset(self, px, py):
        """Turn a pixel off. Out-of-bounds is ignored."""
        if 0 <= px < self.width and 0 <= py < self.height:
            self._lit[py][px] = False

    def line(self, x0, y0, x1, y1):
        """Draw a Bresenham line in pixel coordinates, both ends included."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r):
        """Draw a circle outline with the midpoint circle algorithm. Pixels are square, so this is round on screen."""
        x, y, d = 0, r, 1 - r
        while x <= y:
            for px, py in ((x, y), (-x, y), (x, -y), (-x, -y), (y, x), (-y, x), (y, -x), (-y, -x)):
                self.set(cx + px, cy + py)
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1

    def ring(self, cx, cy, r, thickness=2, gap=None):
        """Light the pixels whose distance from (cx, cy) is in (r - thickness + 0.5, r + 0.5]: a ring with a stroke.

        A one-pixel Braille circle breaks into scattered dots on screen; a stroke two or three pixels thick reads as a
        line. thickness >= r + 1 fills the whole disc. gap=(start_deg, end_deg) leaves that arc unlit; angles are
        measured clockwise from 3 o'clock with y pointing down, so -90 is the top and 90 the bottom.
        """
        lo, hi = r - thickness + 0.5, r + 0.5
        for py in range(max(0, cy - r - 1), min(self.height, cy + r + 2)):
            for px in range(max(0, cx - r - 1), min(self.width, cx + r + 2)):
                d = math.hypot(px - cx, py - cy)
                if not (lo < d <= hi):
                    continue
                if gap is not None:
                    a = math.degrees(math.atan2(py - cy, px - cx))
                    if gap[0] <= a <= gap[1]:
                        continue
                self.set(px, py)

    def plot(self, fn, x0, x1, thickness=1):
        """Draw y = fn(x) for every integer x from x0 to x1 inclusive, as a stroke `thickness` pixels tall.

        Neighbouring columns are joined with line(), so a steep stretch has no holes. The stroke hangs below the
        curve: pixel (x, round(fn(x))) and the thickness - 1 pixels under it.
        """
        prev = None
        for x in range(x0, x1 + 1):
            y = round(fn(x))
            for t in range(thickness):
                if prev is None:
                    self.set(x, y + t)
                else:
                    self.line(prev[0], prev[1] + t, x, y + t)
            prev = (x, y)

    def render(self, trim=False):
        """One string, a row of cells per line; empty cells are U+2800 (not a space).

        By default nothing is trimmed. With trim=True, trailing blank cells are removed from every row and blank
        rows are removed from the top and bottom, which is what a Markdown fence wants. Leading blank cells stay
        U+2800 rather than becoming spaces: a row made only of Braille cells keeps its shape even when the page
        falls back to a Braille font whose cells are wider than the monospaced font's.
        """
        rows = []
        for cell_y in range(self.cells_h):
            row = []
            for cell_x in range(self.cells_w):
                bits = 0
                for (col, r), bit in _BIT.items():
                    if self._lit[cell_y * 4 + r][cell_x * 2 + col]:
                        bits |= bit
                row.append(chr(0x2800 + bits))
            rows.append("".join(row))
        if trim:
            rows = [r.rstrip(chr(0x2800)) for r in rows]
            while rows and rows[0] == "":
                rows.pop(0)
            while rows and rows[-1] == "":
                rows.pop()
        return chr(10).join(rows)
