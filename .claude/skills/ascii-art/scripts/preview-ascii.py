"""preview-ascii.py: render the art blocks of a Markdown file as a GitHub-like page and, with Playwright, screenshot
it at phone and desktop widths and report whether any block would scroll sideways.

Usage:
    python preview-ascii.py FILE.md [--out DIR] [--widths 390,1280] [--html-only]

Writes DIR/preview.html always. With Playwright installed (any interpreter that has it), also writes
DIR/preview-<width>.png per width and prints one line per block and width:
    block 1 @390: 40 columns, fits            (scrollWidth <= clientWidth)
    block 2 @390: 58 columns, SCROLLS by 71px (the reader must scroll the code block sideways)
Exit code 0 when every block fits at every width, 1 when one scrolls, 2 on a usage error. --html-only skips the
browser and exits 0 after writing the page. The page copies GitHub's code-block font stack and sizes as read on
2026-10-05; it is an approximation of GitHub, not GitHub.
"""
import argparse
import html
import sys
from pathlib import Path

ART_INFO = ("", "text", "ascii", "txt")

CSS = """
body { margin: 0; padding: 16px; background: #fff; color: #1f2328;
       font: 16px/1.5 -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif; }
pre  { margin: 0 0 16px; padding: 16px; overflow: auto; background: #f6f8fa; border-radius: 6px;
       font: 85%/1.45 ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace; }
p    { margin: 0 0 16px; }
blockquote { margin: 0 0 16px; padding: 0 1em; color: #59636e; border-left: .25em solid #d1d9e0; }
"""


def extract_blocks(text):
    """Return [(fence_line_number, [lines], following_text_lines)] for every art block in a Markdown string.

    An art block is a fence whose info string is empty or text/ascii/txt. following_text_lines are the non-blank
    lines after the closing fence up to the next blank line or fence, so a preview can show the alt sentence and
    the story under the picture."""
    lines = text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            fence_len = len(line) - len(line.lstrip("`"))
            info = line[fence_len:].strip()
            j = i + 1
            while j < len(lines) and not (lines[j].strip("`") == "" and len(lines[j]) >= fence_len and lines[j]):
                j += 1
            if j >= len(lines):
                break
            if info in ART_INFO:
                k = j + 1
                after = []
                while k < len(lines) and lines[k].strip() == "":
                    k += 1
                while k < len(lines) and lines[k].strip() != "" and not lines[k].startswith("```"):
                    after.append(lines[k])
                    k += 1
                blocks.append((i + 1, lines[i + 1:j], after))
            i = j + 1
            continue
        i += 1
    return blocks


def build_html(blocks):
    """One page: each art block as <pre>, then its following lines (a blockquote stays a blockquote)."""
    parts = ["<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
             "<style>", CSS, "</style>"]
    for n, (_, art, after) in enumerate(blocks, 1):
        parts.append(f"<pre data-block='{n}'>{html.escape(chr(10).join(art))}</pre>")
        for a in after:
            if a.startswith(">"):
                parts.append(f"<blockquote>{html.escape(a.lstrip('> '))}</blockquote>")
            else:
                parts.append(f"<p>{html.escape(a)}</p>")
    return "\n".join(parts)


def measure(page_path, widths, out_dir):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed in this interpreter; wrote the HTML only", file=sys.stderr)
        return None
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w in widths:
            page = browser.new_page(viewport={"width": w, "height": 900})
            page.goto(page_path.resolve().as_uri())
            page.screenshot(path=str(out_dir / f"preview-{w}.png"), full_page=True)
            for n, sw, cw, cols in page.evaluate(
                "() => [...document.querySelectorAll('pre')].map(e => [+e.dataset.block, e.scrollWidth, e.clientWidth,"
                " Math.max(...e.textContent.split('\\n').map(l => [...l].length))])"):
                results.append((n, w, cols, sw - cw))
            page.close()
        browser.close()
    return results


def main():
    ap = argparse.ArgumentParser(prog="preview-ascii.py")
    ap.add_argument("file")
    ap.add_argument("--out", default=None)
    ap.add_argument("--widths", default="390,1280")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()
    src = Path(args.file)
    if not src.is_file():
        print(f"not a file: {src}", file=sys.stderr)
        return 2
    try:
        widths = [int(w) for w in args.widths.split(",") if w.strip()]
    except ValueError:
        print("--widths takes comma-separated integers", file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else src.parent / (src.stem + "-preview")
    out_dir.mkdir(parents=True, exist_ok=True)
    blocks = extract_blocks(src.read_text(encoding="utf-8"))
    page_path = out_dir / "preview.html"
    page_path.write_text(build_html(blocks), encoding="utf-8")
    print(f"{len(blocks)} art block(s); page: {page_path}")
    if args.html_only:
        return 0
    results = measure(page_path, widths, out_dir)
    if results is None:
        return 0
    scrolls = 0
    for n, w, cols, over in results:
        verdict = "fits" if over <= 0 else f"SCROLLS by {over}px"
        scrolls += over > 0
        print(f"block {n} @{w}: {cols} columns, {verdict}")
    return 1 if scrolls else 0


if __name__ == "__main__":
    sys.exit(main())
