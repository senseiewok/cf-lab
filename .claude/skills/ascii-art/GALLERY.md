# ASCII art library

A small gallery of hand-crafted compositions for the Sensei Ewok Lab, and the
design language behind them. Each piece does two jobs at once: it is *surreal
enough to look like a Dalí* (one impossible, precise object standing very still
in an otherwise empty landscape), and it *tells a story like a Paulo Coelho
fable* (a short, quiet sentence underneath that turns the object into a lesson
about the road, the desert, or the treasure).

The structure of every piece is the same, and it is deliberate:

- **The art** lives inside a code fence. It is pure image. No words, no labels,
  no captions inside the fence.
- **The story** is a single blockquote directly beneath the fence. One quiet
  sentence. It is the Coelho line.
- **The notes** after that tell the next agent what may and may not be changed.

Everything here is plain ASCII plus block shading, chosen because it renders the
same on GitHub, in a terminal, and in a diff. The 65 roses are the one place we
use the rose glyph, because the lab has already committed to that specific
symbol; count it exactly wherever it appears.

**The house rule.** One object. One empty field. One line of story. Dalí did not
fill the canvas, and Coelho did not explain the fable. Two things in the picture,
and it stops being an image and starts being a sticker.

---

## How to read the two registers

| Register | Where it lives | What it does |
| --- | --- | --- |
| **Dalí (the object)** | the code fence | one precise, impossible thing, held still; asymmetry on purpose; an object that should not be there but is |
| **Coelho (the story)** | the blockquote under the fence | a sentence that makes the object a small truth about a journey; no explanation, no hype, no slogan |
| **Lab voice (the bridge)** | the surrounding README | warm, peer-to-peer, plain; it hands the reader a move and never promises a cure or a timeline |

A piece is ready when a stranger can say what the object is, *and* retell the
line underneath in their own words. If they can do only one, cut or add until
they can do both.

---

## 1. The Melting Clock

The face is level. The hour has slipped off the edge and is resting. It is the
lab's answer to a deadline, and the piece to use when the subject is patience or
a long build.

```
                  .-~~~~~~~-.
               .- ~ ~~~~~~ ~ -~.
             /                        \
            |     .------------.       |
            |    |    .----.    |      |
            |    |    |  | |    |      |
            |    |    '--'     |      |
            |     '------------'      |
             \                        /
                '-.__________.-'
                    ~  ~  ~
                      ~  ~
                        ~
                          ~
```

> *The hand has let go of the hour. Some things are done when they are true, not
> when they are early.*

Notes: the clock is level; only the lower-right edge has a long drip, and that one
droop is the whole joke. Do not add a second hand, gears, or a shadow. They turn
it back into a clock instead of a thought about time.

---

## 2. The Eye

One eye, fully open, in a field of blank space. The piece for "we check the work
before we call it done," and for any README whose subject is verification or
review.

```
                 .-"""-.
             .-"""-"""-"""-.
          .-"""-"""-"""-"""-"""-.
        .-"""-"""-"""-"""-"""-"""-.
        |      .-""""""-.      |
        |      | .-----. |      |
        |      | |  ()  | |      |
        |      | '-..-' | |      |
        '      .--------.      '
        '-"""-"""-"""-"""-"""-"""-
           '-"""-"""-"""-"""-.
               '-"""-"""-.
```

> *Open the eye before you open the mouth. The first look is the cheapest one you
> will ever take.*

Notes: keep the iris a small, calm ring. A cluttered or starburst iris reads as a
meme; a quiet one reads as a portrait.

---

## 3. The Tree of Thought

The mission, drawn. The canopy reaches up toward the people the work is for; the
roots reach down into the code that powers it. One tree, two directions. This is
the default banner when the subject is the lab itself.

```
                 .  *  .  *  .  *  .
           *  .  *  *  *  *  *  .  *
               *  *  *  *  *  *  *  *
             *  *  *  *  *  *  *  *  *
               *    *     *     *    *
                  |        |
             +----+        +----+
             |                |
             +--------+-------+
                    |
            +-------+-------+
            |              |
            +------+-------+-----+
                   |
                +--+--+
                |  |  |
```

> *A machine is only a branch. It is the tree we are growing together that
> decides what is fruit and what is just wood.*

Notes: the trunk is a single vertical line; the canopy is the upper cluster of
`*`; the roots are the three descending tiers of `+---+`. Count the tiers and
stop. If it starts to look like a flowchart, remove a tier.

---

## 4. The Alchemist's Road

The Coelho piece. A long, empty desert, one straight road, and one small distant
shape at the end of it. Use it for research notes, benchmarks, or anywhere the
message is that the work itself is the point.

```
                        (   )
                     (  * * *  )
                   (  (       )  )
                (  (   (  *  )   )  )
               (  (  (  (    )  )  )  )
              (  (  (  (  *  )  )  )  )
             (  (  (  ( ( ( ) )  )  )  )
             (  (  ( ( ( ( ) )  )  )  )
              (  (  ( (   )  )  )  )
               (  (  (  )  )  )
                (  (   )  )
                 (  (  )
                   ( )
                    (
                    (
                    (
```

> *You will cross the desert to find what you already carry. That is not a
> disappointment. That is the whole point of crossing.*

Notes: the road is the single straight spine; the small triangle is the distant
shape, and it is *small on purpose*. Leave the desert empty. A full desert is a
poster; an empty desert is a story.

---

## 5. The Long-Necked Bird

A Dalí creature: very long, very patient, looking down the road. The piece for
patience, for the long build, for the day the loop is still running and
everything else is quiet.

```
                        .
                     .--'
                    /  '
                    |
                    |
                    |
                    |
                    |
                    |
                    |
                  .-+-.
                 /     \
                /  () () \
                \  '' ''  /
                 '-.---.-'
                    |  |
                   /    \
                  /      \
```

> *Some things are not slow. They are only tall, and looking at a longer road than
> the one you can see from where you stand.*

Notes: the neck is a single straight column. Do not curl it. The stillness is the
bird; a wavy neck turns it into a doodle.

---

## 6. The 65 Roses

The tribute. Sixty-five roses in total, never rounded, never fewer, never more.
The name comes from a child's pronunciation of the disease, as the Foundation
tells it; this is an independent tribute, not an emblem, an endorsement, or an
affiliation. Count the glyph in the *rendered* output every time this is
reproduced anywhere in the workspace.

```
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  +-------------------------------------+
  |         S E N S E I   E W O K       |
  |                L A B                |
  +-------------------------------------+
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
  🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹 🌹
```

> *We do not make medicine and we do not claim a cure. We stand on the ground the
> pioneers made, and we do the next useful piece of the work. That is all, and it
> is enough.*

Notes: five rows of thirteen, above and below, so the total is five times
thirteen, sixty-five. Verify that total in a rendered preview, not by character
length. Respect reduced-motion if the field is ever animated. Do not imply
affiliation with the Foundation.

---

## 7. The Held Breath

One bubble, a little above a long flat horizon, its shadow fainter than it is. Use it when the subject is lightness: care, a thing carried without gripping, a pause that is allowed. It is the first piece composed on a grid with `scripts/asciicanvas.py` (recipe: `scripts/examples/held_breath.py`) and the first to use Braille.

```
              ⣀⡠⠤⠤⠤⣀⡀
            ⡠⠊⢀⣠⠄   ⠈⠢⡀
           ⡎ ⡴⠋       ⠈⡆
          ⢸  ⠁         ⢸
          ⠸⡀           ⡸
           ⠣⡀         ⡠⠃
            ⠈⠢⣀⡀   ⣀⡠⠊
               ⠈⠉⠉⠉


    ______________________________________
        ..::---=====---::..
```

> *Some things are carried best when you do not grip them.*

Notes for the next agent:

- **Description for screen readers** (put it where the page needs it): a single soap bubble, drawn in Braille dots, floats above a long flat horizon line; a faint shadow lies on the ground beneath it.
- The bubble is off centre on purpose, and the horizon runs past it to the right. Keep one bubble. A second one makes a sticker.
- Braille draws fainter than other glyphs and some fonts give it a different width. Preview it where it will be shown; if it breaks, fall back to piece 5 or 6.
- Made 2026-10-05 as a demonstration of the process in SKILL.md sections 6 and 7. A human reads it before it appears on anything CF-facing: the lab does not tell people with CF what to do with their breath, and this piece must not read as if it did.

---

## 8. The Open Loop

One ring that does not quite close, and a small stone waiting outside the gap. The piece for the control repository and for any subject that is a loop with a gate in it: a review cycle, a task board where a model proposes and a person moves. Recipe: `scripts/examples/open_loop.py` (Braille `ring` with a gap; the first piece to use strokes instead of one-pixel lines).

```text
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣄
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⠶⠟⠛⠛⠛⠷⠆⠀⠀⠀⠘⠿⠟
⠀⠀⠀⠀⠀⠀⠀⠀⢠⡾⠋
⠀⠀⠀⠀⠀⠀⠀⢠⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤
⠀⠀⠀⠀⠀⠀⠀⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⡇
⠀⠀⠀⠀⠀⠀⠀⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇
⠀⠀⠀⠀⠀⠀⠀⠹⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡿⠁
⠀⠀⠀⠀⠀⠀⠀⠀⠹⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡾⠁
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠶⣤⣄⣀⣀⣀⣤⡴⠞⠋
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠉⠉⠁
```

*A ring of Braille dots, not quite closed, floats in an empty field; a small round stone waits just outside the gap at its upper right.*

> *A loop is a circle that stops to ask before it closes.*

Notes: the gap is upper right and the stone sits on the ring's own radius line, a little further out; both are the asymmetry. The ring is a two-pixel stroke on purpose: a one-pixel Braille circle (the 2026-10-05 first draft) rendered as scattered dots. Keep one stone. Used at the top of the `cf-lab` README from 2026-10-05, 25 columns, fits a phone.

---

## 9. The Measured Line

A curve drawn solid only where there are measured points, and single dots where there are none. It echoes the lab's CFTR model page, where a stretch no structure places is a dotted connector, not a shape. Use it for a note or a tool whose honesty is in saying where the data stops. Recipe: `scripts/examples/measured_line.py` (Braille `plot` with a three-pixel stroke).

```text
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⡆⢀⠀⡀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⠟⠉⠀⠀⠀⠀⠈⠀⠂⠀⠂⠠⠀⡀⢀⠀⡀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡾⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⣦⡀
⠀⠀⠀⠀⠀⠀⠀⣠⡾⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣦⡀
⠀⠀⠀⠀⣀⣴⠿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⢷⣄⡀
⠀⣤⣴⡾⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠻⣶⣤
⠀⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉
```

*A single arch-shaped line crosses an empty field, drawn solid at both ends and left as a row of single dots across the top.*

> *A line goes only as far as the measuring went. After that, dots, and saying so.*

Notes: the crest is right of centre and the dotted stretch is straight, a connector and not a shape. Do not curve the dots to "complete" the arch; the point is that nobody measured it. Drawn 2026-10-05 for the research README and then set aside for piece 11, which the maintainer chose; 40 columns.

---

## 10. The Lantern

One hanging lamp, lit, in an empty field, in plain line characters placed cell by cell. The piece for the skills repository and for anything handed from one pair of hands to another. Recipe: `scripts/examples/lantern.py` (Canvas only; no Braille, so it renders the same everywhere).

```text
                         .
                         |
                         |
                       _.|._
                      /     \
                     |       |
                     |   .   |
                     |  (:)  |
                     |   '   |
                     |       |
                      \_____/
                        '-'
```

*A single hanging lantern, drawn in plain line characters, hangs from a short chain in an empty field with a small flame inside.*

> *Whoever lit the lamp is not the one who reads by it.*

Notes: the lamp hangs right of centre; the chain is short so the lamp, not the chain, is the object. The flame is three glyphs and stays three. Used at the top of the `cf-skills` README from 2026-10-05, 30 columns, fits a phone.

---

## 11. The Threaded Gap

A long gentle double helix with one small gap in one strand, and a thin thread curving up toward it from the lower right. The maintainer's choice for the research repository, as an echo of the CFTR model page, where residue 508 is marked and shown as a gap in two of the four structures. It is an emblem of the work of understanding and checking, not a diagram of a gene, a protein or a treatment, and the text around it must say so. Recipe: `scripts/examples/threaded_gap.py` (near strand a two-pixel `plot` stroke, far strand single dots hidden at the crossings, the thread a quadratic curve of dots).

```text
⠀⠀⠀⠀⠀⡀⠄⠂⠂⠁⠁⠛⠛⠶⢦⣄⡀⠀⠀⠀⠀⠀⠀⠀⡀⠄⠂⠂⠁⠁⠛⠛⠶⢦⣄⡀⠀⠀⠀⠀⠀⠀⠀⡀⠄⠂⠂⠁⠁⠛⠛⠶⢦⣄⡀
⠀⠀⠀⠄⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⠶⣄⠀⠀⠀⠄⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⠶⣄⠀⠀⠀⠄⠂⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⠶⣄
⠀⢦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢦
⠀⠀⠈⠳⢦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠂⠁⠀⠀⠈⠳⢦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠂⠁⠀⠀⠈⠳⢦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠂⠁
⠀⠀⠀⠀⠀⠉⠛⠶⢦⣤⣤⡄⠄⠂⠂⠁⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠆⠀⠀⠄⠠⠀⠒⢆⠁⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠶⢦⣤⣤⡄⠄⠂⠂⠁
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠑⠢⠄⣀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠂⠒⠤⠄⠤⣀⡀⣀⡀
```

*A double helix drawn in Braille dots twists gently across an empty field; one strand has a small gap near the middle, and a thin thread curves up toward it from the lower right.*

> *Into the gap we work a thread of questions, slowly, and check each one before the next.*

Notes for the next agent:

- The story and the description say "work", "questions" and "check"; they never say repaired, mended, fixed, cured or will. Keep it that way. The gap is a place in the picture, not a prognosis, and the README sentence beside it says the picture is an emblem.
- The first draft (2026-10-05) had both strands on one equation and sparse rungs between them; it rendered as one wave with dirt. Only the PNG showed it. The far strand is single dots and vanishes at each crossing; that is what makes it read as depth.
- 59 columns: on a 390 px phone the code block scrolls sideways by about 214 px; the gap and the thread are inside the left 39 columns, so a phone sees the focal point. Used at the top of the `cf-research` README from 2026-10-05.

---

## Combining pieces

- **One piece per banner.** A README banner is a single image with a single story
  line. Two pieces side by side read as two different projects.
- **Match the piece to the subject.** The lab itself: the Tree of Thought.
  The control repository, or any loop with a gate: the Open Loop. Research notes
  or benchmarks: the Alchemist's Road or the Eye; where the data stops: the
  Measured Line; the CFTR work: the Threaded Gap, with its emblem sentence.
  Things handed on: the Lantern. Lightness or care: the Held Breath. Patience or
  a long build: the Melting Clock or the Long-Necked Bird. The tribute, wherever
  the CF community is addressed: the 65 Roses. Do not put the Melting Clock over a
  patient-facing sentence; its humor is not the register that line needs.
- **Each README opening uses two of these at most**: one new piece at the very
  top and, in `cf-lab`, the 65 Roses as the tribute inside the community letter.
- **Keep the object, swap the story.** The same tree can carry a different line in
  a different repo. The object is the brand; the line is the context.
- **Keep the two layers separate.** The surreal object and the fable line are two
  different things. Never write the story inside the code fence, and never
  decorate the fence with words.

## Verification (run before a piece ships)

1. Render it in a real Markdown preview at desktop width and at a narrow phone
   width (`python scripts/preview-ascii.py FILE.md` screenshots both and says
   which blocks scroll). The pieces here are designed near 40-60 display columns
   and never over 72; about 39 fit a 390 px phone without a sideways scroll, so
   a wider piece keeps its focal point on the left and says that it scrolls.
2. Count any repeated motif in the *rendered* output (the 65 roses, the root
   tiers). Never count by `.Length`; emoji and Unicode are not single columns.
3. Confirm there are no ANSI escape bytes, no control characters, and no stray
   tabs inside the fence.
4. Read the story line aloud. If it sounds like a slogan or a caption, it is not a
   Coelho line; make it quieter and shorter.
5. For any CF-facing use, re-run the `cf-research-context` and `lab-voice` gates:
   person-first, no cure or timeline promised, the 65 count exact, no implied
   Foundation affiliation.
