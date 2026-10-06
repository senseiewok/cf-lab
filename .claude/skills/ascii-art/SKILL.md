---
name: ascii-art
description: Design and generate artistic ASCII art for READMEs, banners, and terminals — a lab gallery of Dalí-quiet, Coelho-story compositions (melting clock, eye, tree of thought, alchemist's road, long-necked bird, the 65 roses, held breath, open loop, measured line, lantern, threaded gap), a craft process, a small canvas library (asciicanvas.py) for composing on a grid, generated fences (place-art.py), a rendering and accessibility checker (check-ascii.py), a phone-and-desktop preview (preview-ascii.py), the shape of a README opening block with its screen-reader sentence and community letter, figlet fonts, ANSI styling, box-drawing, block shading, Braille, and rendering caveats for GitHub.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# ASCII art

Use this skill when asked to make a README banner, logo, title art, or any "ASCII art" — especially surreal, artistic, or "epic" styles. It covers the lab's own art library, the design language behind it, the real libraries you can call to *generate* the art, the hand-crafted techniques for *designing* it, and the rendering rules that keep it looking right on GitHub.

## 0. Tone and story: the Dalí / Coelho register

The lab's house style for banners is to look like a **Dalí** and tell a story like a
**Paulo Coelho**. Concretely:

- **Dalí (the object).** One precise, impossible thing, held very still, in an
  otherwise empty field. Asymmetry on purpose. No clutter, no second focal object,
  no drop shadow, no label. Dalí left most of the canvas empty; so do we.
- **Coelho (the story).** One quiet sentence that turns the object into a small
  truth about a journey: the road, the desert, the patience, the treasure. No hype,
  no slogan, no explanation. If the line reads like an ad, it is too loud.
- **Two layers, kept apart.** The art lives inside the code fence as pure image.
  The story is a single blockquote beneath the fence. Never write the story inside
  the fence, and never decorate the fence with words.
- **In the lab voice.** The surrounding README text is warm, peer-to-peer, and plain
  (see `lab-voice`). It never promises a cure or a timeline, and it hands the reader
  a move. Load `cf-research-context` before any CF-facing banner.

Start from the library in **[GALLERY.md](GALLERY.md)** rather than inventing a style
from scratch. Pick the piece that matches the subject, swap the story line to the
context, and verify the render. Only fall back to the generated-text tools below
(§2) when you specifically need big stylized *lettering* rather than an object.

## 1. Choose a path

| Goal | Best tool |
| --- | --- |
| Big stylized *text* logo | figlet-style generator (`pyfiglet`, `cfonts`, `art`) |
| Animated / colored terminal output | `cfonts`, `terminaltexteffects`, `asciimatics` |
| Turn a real image into ASCII/Braille | `TheZoraiz/ascii-image-converter` (Go) |
| Hand-crafted banner with boxes/shading | Do it by hand (see §4) — most control, best result |

For a README, choose the treatment from the reader and the message, not a default cyberpunk recipe. Compare a compact hand-crafted mark with generated lettering if useful; neither method is automatically better. For a community letter, quiet framing and breathing room can carry more feeling than dense shading or fake binary data. Use `lab-voice` for the words and `cf-research-context` for a CF tribute.

## 2. Library catalog (generate the art for you)

Pick by language; all are open source on GitHub.

| Library | Language | Install | Notes |
| --- | --- | --- | --- |
| `sepandhaghighi/art` | Python | `pip install art` | 1800+ fonts, `art.print_art("SENSEI","block")` |
| `pwaller/pyfiglet` | Python | `pip install pyfiglet` | classic figlet fonts, `.figlet("text")` |
| `xero/figlet-fonts` | fonts | clone | the font files the generators load |
| `dominikwilkowski/cfonts` | Node | `npm i cfonts` | ANSI colors/shades, `cfonts.log("hi")` |
| `ChrisBuilds/terminaltexteffects` | Python | `pip install terminaltexteffects` | animations, rain, glitch, 3D |
| `peterbrittain/asciimatics` | Python | `pip install asciimatics` | screens, effects, `FigletText` |
| `drewnoakes/figgle` | .NET | `dotnet add package Figgle` | figlet for C#/.NET |
| `yuanbohan/rs-figlet` | Rust | crate `rs-figlet` | figlet in Rust |
| `mbndr/figlet4go` | Go | `go get .../figlet4go` | figlet in Go |
| `arsham/figurine` | Go | `go get .../figurine` | figlet + fonts in Go |
| `TheZoraiz/ascii-image-converter` | Go | `go install .../cmd/...` | image → ASCII/Braille with palette |

### Tool use

The catalog is a discovery aid, not verified installation/API guidance. Check the selected tool's official README, licence, current command, and availability before use. Follow `security-browsing` for research and `security-baseline` before adding dependencies; don't install globally or clone a font collection just to make a small banner. Prefer already available tooling or a hand-crafted composition. Source material and generated output still need review.

## 3. Terminal / color notes

- ANSI color codes (`\x1b[38;5;n m`) only render in a real terminal or on platforms that decode them (e.g., some CI logs, Neovim grids). **GitHub Markdown code blocks do NOT render ANSI escapes** — you will see literal escape bytes. So for a README banner, use *shape and Unicode*, not color.
- UTF-8 symbols and emoji depend on fonts, platform, and renderer. They are not guaranteed to share a monospaced cell width. Avoid raw ANSI sequences in committed READMEs.
- `cfonts`/`terminaltexteffects` shine when *running*, not when committed — use them to prototype, then paste the clean output.

## 4. Designing a banner by hand (the good stuff)

GitHub renders these Unicode characters in a monospaced code block. Combine them:

- **Box drawing** `╔ ╗ ║ ╚ ╝ ═ ╣ ╠ ╦ ╩ ╬` — frames, dividers.
- **Block shading** `░ ▒ ▓ █` — gradients, "depth," scanline feel.
- **Braille** `⠿ ⢿ ⣿ ⣾ ⣷ ⡿ ⠻` — high-res pixel art and "signal" texture.
- **Emoji / glyphs** `🌹 ✦ ◆ ▮ ⚡` — accents and signature motifs.
- **Binary / hex** `01101001` — a cyberpunk "data" read.

### Rules that keep it from looking broken

1. **Design for the actual container.** Start near 40-60 display columns for a README and never pass 72; this is a design budget, not a GitHub guarantee. Measured 2026-10-05 in the GitHub-like page `scripts/preview-ascii.py` builds, at 390 px: about 39 columns fit a code block without a sideways scroll, 49 columns scroll by 40 px and 62 by 252 px. GitHub never wraps a code block, so a wider piece scrolls; put the focal point in the left 39 columns so a phone still sees it, and say in the report that it scrolls. Character count, UTF-16 length, grapheme count, and rendered width are different measurements.
2. **Count your motif.** If the design is "65 roses," count them. A 5×13 grid = 65. Off counts read as a bug, not a choice.
3. **Separate decoration from alignment.** Put emoji motifs in free-standing bands, not between frame edges. Prefer ASCII `+`, `-`, and `|` for a portable frame; Unicode shading and Braille are optional, renderer-dependent accents. Include a normal-text title and explanation outside the art for accessibility.
4. **Left-pad** with spaces so the art sits inside the code fence, not flush against it.
5. **Verify rendered.** Inspect the final Markdown preview at desktop and mobile widths. `gh repo view` output is not a visual rendering check. A local preview approximates GitHub; label that limitation rather than uploading unpublished content merely to verify it.

### The lab banner (the 65 roses)

The default lab identity banner is in **[GALLERY.md, piece 6](GALLERY.md#6-the-65-roses)**. It uses a portable `+---+` frame with the SENSEI E WOK / LAB title inside, flanked by three rows of roses above and below. Total: exactly 65.

When reusing or adapting it:

- Keep the count at 65, never rounded.
- Prefer the ASCII `+`, `-`, `|` frame for portability; block-shading (`░▒▓█`) and Braille (`⣿`) columns are optional accents that may not render in every terminal or diff viewer.
- Remove arbitrary binary strings or decorative data strips when they compete with the title or the CF message.
- Preserve an already-approved motif when changing the frame; do not replace community symbolism with an unrelated mascot.

## 5. Verification step

After writing banner art into a file:

0. Run `python .claude/skills/ascii-art/scripts/check-ascii.py <file> --max-width 60`. It fails on tabs, control characters, invisible format characters (a zero-width space or word joiner takes no column and shows nothing; one was found in a fence that had been retyped by hand on 2026-10-05, which is why fences are generated, see §7), lines wider than the limit, a misaligned frame, and art with no text description after it; it warns on trailing spaces and wide glyphs. It does not judge beauty, and it cannot tell a good description from a bad one.
0b. Run `python scripts/preview-ascii.py <file>` with an interpreter that has Playwright (`--html-only` without one). It writes a GitHub-like page, screenshots it at 390 and 1280 px, and prints per block whether it fits or scrolls. Open the PNGs and look: a one-pixel Braille circle reads as scattered dots, a formula error can make two strands one, and neither shows in the text.
1. Reopen it and **count** any repeated motif explicitly (e.g. "5 rows × 13 = 65") — never estimate.
2. Measure ASCII-only frame lines for matching edge positions; check Unicode/emoji visually, not by `.Length` alone.
3. Inspect the final rendered state at representative widths; confirm no ANSI/control bytes, clipped text, or unintended page overflow. Keep screenshots local and private. Report a missing visual check explicitly.
4. If a motif count is wrong, fix it in one targeted edit and re-verify — don't ship a partial fix.

The 2026-10-03 session review exposed unreliable claims based on character counts and screenshots of the wrong state. A passing count check establishes the count only; it does not establish visual quality or accessibility.

## 6. Make it art: a process an agent can follow

The goal is a piece a person would stop and look at, not generated lettering. Craft is a sequence of decisions; make them in this order and write each answer down before placing a character.

1. **One idea.** The object, the empty field and the one-sentence story from section 0. If you cannot say it in a sentence, stop.
2. **Silhouette first.** Draw the outline in one line weight before any tone. Joan Stark, among the most prolific free-hand ASCII artists of the 1990s and 2000s, worked in a "line style" that one appreciation compares to the *ligne claire* of comics. Add tone only where it carries meaning.
3. **Know where characters sit.** Stark's tutorial: "The periods, commas, and underscores are at the bottom of the character space. The hyphen, equal sign, and the plus sign are found in the middle of the space." Use that to place a horizon (a low `_`, a mid `-`) and to step a slope through `_ , . - ' " ^`.
4. **A small palette per piece.** Choose five to nine glyphs on purpose, such as a density ramp ` .:-=+*#%@` or a shorter one, and keep to it. A short ramp reads as a decision; a long one reads as a photo filter. Note what each glyph is for.
5. **One focal point, one contrast.** One dense area against open space; one smooth texture against one grainy one. A second competing focus makes a sticker (the house rule in GALLERY.md). Leave room: a web summary I did not verify suggests 40 to 60 percent whitespace for clean marks; treat that as a prompt to look, not a measure.
6. **Asymmetry on purpose.** Build a symmetric object with `mirror_x`, then break the symmetry once, where the eye should go.
7. **Look, then describe it in words.** Render, then say what you see to someone who cannot see it: what is it, where is the weight, what is the empty part? If the description differs from the intent, change the picture. Reading your own output is reliable; judging it by drawing it again is not (next section).
8. **Stop.** Two or three rounds. Keep each round's render so a regression is visible.

## 7. Compose on a grid, not freehand

Models read ASCII better than they draw it. An April 2026 arXiv paper (Huang, Liu, He and Gilpin) reports a "Read-Write Asymmetry": language models interpret ASCII representations effectively but struggle to produce them from text, and training on constructing layouts improved spatial reasoning. LTD-Bench (Lin and others, November 2025) found "profound deficiencies in establishing bidirectional mappings between language and spatial concept" when models draw. The practical rule: do not type a whole picture in one shot. Place marks at exact coordinates, render, read the result back, adjust.

`scripts/asciicanvas.py` (standard library only) does the placing:

```python
import sys
sys.path.insert(0, ".claude/skills/ascii-art/scripts")
from asciicanvas import Canvas, Braille

c = Canvas(40, 12)
c.hline(2, 9, 36, "_")                                   # a horizon
c.ellipse(14, 4, 8, 4, "o")                              # cells are about twice as tall as wide: ry = rx / 2
c.fill_ramp(4, 10, 20, 1, lambda x, y: 1 - abs(x - 14) / 10, ramp=" .:-=")   # a soft shadow
print(c.render())

b = Braille(20, 6)                                       # 40 x 24 pixels, 2 x 4 per character
b.circle(20, 12, 11)
b.line(0, 23, 39, 23)
print(b.render())
```

`Canvas` has `put`, `text`, `hline`, `vline`, `line` (the glyph follows the slope), `rect`, `ellipse`, `fill_ramp`, `stamp` and `mirror_x`; `Braille` has `set`, `unset`, `line`, `circle`, `ring` (a stroke of chosen thickness, with an optional unlit arc) and `plot` (y = f(x) as a stroke, columns joined so a steep stretch has no holes), and `render(trim=True)` for a fence (blank rows and trailing blank cells removed, leading cells kept as U+2800 so the shape survives a Braille fallback font). `python scripts/test-asciicanvas.py` runs its checks. It knows nothing about fonts, so look at the result where it will be shown. Gallery pieces 7 to 11 were composed this way; their recipes are in `scripts/examples/`.

Lessons from pieces 8 to 11 (2026-10-05):

- **Generate the fence, never retype it.** `python scripts/place-art.py RECIPE.py FILE.md [--block N]` runs a recipe and writes its output into the Nth art fence of a Markdown file, trailing spaces stripped. A fence retyped by hand picked up a word joiner; the checker now fails on those.
- **In Braille, a line is a stroke.** A one-pixel circle or curve breaks into scattered dots on screen. Use `ring(..., thickness=2)` and `plot(..., thickness=2 or 3)`; keep single dots for what is meant to read as dots (a far strand, an unmeasured stretch, a thread).
- **One formula, two strands.** The first helix drew both strands with the same equation and looked like one wave with noise; only the PNG showed it. Read the render back and name the parts you see; if a part is missing, the recipe is wrong, not the font.
- **Decoration becomes noise fast.** Sparse "rungs" between helix strands read as dirt at README size and were cut. One object, one accent (the gap and its thread), nothing else.
- **Keep the recipe with the piece.** Each gallery entry names its recipe, so a regression is a diff in a script, not a retyped picture.

## 8. Finer than a character: block elements and Braille

The Block Elements range (U+2580 to U+259F) gives halves, quadrants and three shades, and its glyphs "each share the same character width in most supported fonts, allowing them to be used graphically in row and column arrangements". Braille (U+2800 to U+28FF) gives 2 by 4 dots per character, the smoothest curves available in plain text, but it draws fainter than other glyphs and some fonts differ. The sextant and octant mosaics in the Symbols for Legacy Computing block have patchy font support (from search results, not verified here). Portable README art stays mostly ASCII with a few block or Braille accents; richer pieces suit terminals you control. Preview where it will be shown.

## 9. Accessibility

The W3C technique for ASCII art (H86) says: "If ASCII art is used, it should also have a text explanation of what the picture is." It warns that such art "can be very confusing to people who are accessing the internet using screen readers". In a README, the line after the fence says in plain words what the picture shows; the Coelho line may do both jobs only if it names the object. In HTML, a container with `role="img"` and an `aria-label` gives a screen reader one sentence instead of a string of punctuation (a technique from search results, not read at the source). `scripts/check-ascii.py` fails on art with nothing prose-like after it, which is a floor, not a standard.

The lab's shape, used in the three README openings of 2026-10-05: the fence, then one italic sentence directly under it, then the story as a blockquote. The italic sentence is the description: name the object, the medium ("Braille dots", "plain line characters"), where the weight is and where the empty part is, in one sentence a listener could draw from ("A ring of Braille dots, not quite closed, floats in an empty field; a small round stone waits just outside the gap at its upper right"). It describes, it does not interpret; the story line interprets, and it stays separate. Keep both in `GALLERY.md` with the piece, so the description is written once and reused.

## 9b. A README opening block

What the maintainer asked for on 2026-10-05, and what worked: art at the very top, a one-line promise of what the repository is, in bold, ending "Research, not medical advice."; then **What this is** (a few short paragraphs a newcomer can follow, with a plain "What this is not"), **Try it** (only commands the repository's own READMEs give, with what each does), **What's inside** (a pointer to the existing table, not a copy), **How we check it** (tests, gates, reviews, and where each published number comes from), then **To our CF community**. The block is added around the existing README; every existing fact, table and link stays.

- **Counts come from files, dated, with the command.** "53 sources on 2026-10-05, counted from the file", "98 entries by `ledger/tally.py`", "88 tasks, counted from `board.json`". No number that is not in a file or a command's output.
- **The letter is short and warm, to peers.** People living with CF, families, caregivers and researchers; what is here, what it is for, what it is not (not medicine, not advice), one concrete invitation (open an issue and quote the sentence; read the model's wording before it leaves draft). The roses are the tribute, exact and independent of the Foundation. "You deserve care, dignity and room for ordinary life, and you owe no one an inspiring story" is the one sentence of encouragement; nothing presses anyone to be resilient.
- **Words that stay out of public text:** miracle, warrior, battle, fight, hero; a cure or a timeline promised (saying "we do not claim a cure" is allowed); medical advice; any statement, denial or hint of the maintainer's personal connection to CF; conference or contact details; email addresses.
- **The art may echo the science without claiming it.** The threaded gap echoes residue 508 on the CFTR model page; its description and story say it is the work of understanding and checking, never that anything has been or will be repaired, and the text beside it says the picture is an emblem, not a diagram of a gene or a treatment.
- **Anchors to the host README** (`#how-the-work-is-divided`) will show as broken links in the scratch file; they resolve once the block is placed. Say so in the placement comment at the top of the block.

## 10. Sources read on 2026-10-05, and how far to trust them

| Source | What it gave | How it was read |
| --- | --- | --- |
| arXiv 2604.14641 (Huang, Liu, He, Gilpin, April 2026) | Read-Write Asymmetry | abstract page, quotes checked verbatim |
| arXiv 2511.02347 (LTD-Bench, November 2025) | Drawing tests of spatial reasoning | abstract through a summarising fetch tool; not byte-checked |
| W3C WCAG technique H86 | Text alternatives for ASCII art | page, quotes checked verbatim |
| Joan Stark's tutorial (mirrored at ludd.ltu.se) | Where characters sit, interchangeable glyphs, free-hand practice | page, quotes checked verbatim |
| Velvetyne, "About ASCII art and JGS font" | Stark's line style and the *ligne claire* comparison | summarising fetch tool; not byte-checked |
| Wikipedia, Block Elements | Sub-cell glyphs and their widths | page, one quote checked verbatim |
| Web search summaries (ANSI scene history, density ramps, negative space, sextants) | Background | search summaries only; unverified. Use for orientation, never as a claim |

The sample is small and the research was one session. It shows where models are weak at drawing and which craft habits professional ASCII artists describe; it does not show that following this process makes better art. The test of that is a stranger's reaction to the piece (section 0), not a script.
