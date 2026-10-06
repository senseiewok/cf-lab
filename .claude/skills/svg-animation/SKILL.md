---
name: svg-animation
description: Techniques for animating SVG on the web - CSS transitions and keyframes, the Web Animations API, SMIL, line drawing, path morphing, and the accessibility, reduced-motion and Content-Security-Policy rules that go with them, with a tested example. Use when the user asks to animate an SVG, logo, icon, diagram or vector illustration on the website.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# SVG animation

Inline SVG when page CSS or JavaScript needs to address its internal elements. An SVG loaded through `<img>` is isolated from the parent document's CSS and DOM, but its own declarative animation may still run, and image embedding disables script in it. Inline only trusted, first-party SVG, or sanitize untrusted SVG first.

## How this skill relates to Anthropic's skills

This is a thin layer. It copies nothing from them and works alone.

| Base (third party, install separately if you want it) | What it gives | What this layer adds |
| --- | --- | --- |
| `frontend-design` and `algorithmic-art` from Anthropic's public skills (github.com/anthropics/skills, Apache-2.0, reviewed commit 8a1541c, 2026-09-28; not part of this repo) | Visual direction and craft; seeded, reproducible generative art | Reduced-motion and pause rules, accessible names, no third-party scripts, calm visuals for CF-facing pages, sourced practice, and an example proved in a real browser |

The `algorithmic-art` template loads p5.js from a CDN and carries Anthropic branding; do neither on a lab site. See `THIRD_PARTY_SKILLS.md` in the control repo.

## Choosing a technique

| Technique | Best for | Notes |
| --- | --- | --- |
| CSS `transition` and `@keyframes` | Simple hover and loop effects | No JavaScript. Limited to properties CSS can animate; cannot react to runtime conditions on its own. `animation-play-state` pauses and resumes |
| Web Animations API (`element.animate()`) | The same effects with scripted control: play, pause, reverse, speed, a `finished` promise | No library. `document.getAnimations()` lists what is running, which makes tests deterministic |
| SMIL (`<animate>`, `<animateTransform>`) | Declarative animation that travels inside a self-contained SVG | MDN lists `<animate>` as widely available and shows no deprecation notice; SVG 2 moved animation into its own module and did not remove it. `pauseAnimations()` pauses SMIL only, not CSS or WAAPI animations, so a pause control for a mixed SVG must handle each system |
| GSAP (and its morph plugin) | Complex sequencing, path morphing, scroll timelines | A dependency, and its licence is not an OSI open-source licence; read its current terms before use or redistribution |

Default to CSS for simple effects. Path morphing needs the two paths to have the same number and type of commands; the CSS `d: path()` property needs the same, and MDN marks it as not widely available, so test the target browsers or use a tested library.

## What is cheap to animate

- Prefer `transform` and `opacity`. web.dev advises animating only those so the work stays on the compositor, and keeping away from layout properties such as `top`, `left`, `width` and `height`. Do not assume SVG children are compositor-only; profile when it matters.
- Official sources read give no performance figure for SVG `filter` or for attributes such as `d` and `stroke-dashoffset`. Treat their cost as unknown and measure on the slowest target device. Avoid animating `filter` in a tight loop.
- Use `will-change` sparingly.

## The line-drawing effect

Keep the path fully visible by default and enable the drawing only when reduced motion is not requested. `examples/line-draw.html` is a complete, tested page:

```css
.draw-path { stroke-dasharray: none; stroke-dashoffset: 0; }
@media (prefers-reduced-motion: no-preference) {
  .draw-path { stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 2s ease forwards; }
}
@keyframes draw { to { stroke-dashoffset: 0; } }
```

Set `pathLength="1"` on the `<path>` so dash values are measured against 1 whatever the real length (our inference from MDN's description of `pathLength`). `pathLength` is listed on `circle`, `ellipse`, `line`, `path`, `polygon`, `polyline` and `rect`.

## Reuse and structure

- Reuse a `<symbol>` or `<g>` with `<use href="#id">`. A `<symbol>` is only drawn through a `<use>` and can carry its own `viewBox`. The copied content sits in a tree page CSS does not reach, so style it with inheritance (custom properties, `currentColor`). Browsers may require same-origin for external `<use>` references.
- Group related shapes with `<g>` and animate the group. Set `transform-box: fill-box` and `transform-origin` when rotating or scaling.
- `viewBox` maps the drawing to its box, and `preserveAspectRatio` defaults to `xMidYMid meet`. Give the `<svg>` a `viewBox` and let CSS set its size.

## Accessibility and motion

- Provide a static result by default and add non-essential animation only inside `@media (prefers-reduced-motion: no-preference)`. In JavaScript, check the same preference with `matchMedia` and stop when it changes. `@media (prefers-reduced-motion)` with no value means the same as `reduce`. This project is stricter than the standard, which allows toning motion down: only do that deliberately, and prefer opacity changes over movement.
- Motion that starts by itself, lasts more than five seconds and sits beside other content needs a pause, stop or hide control (WCAG 2.2.2). No more than three flashes in any second (2.3.1). Motion caused by interaction should be switchable off (2.3.3, level AAA). Controls are ordinary buttons, at least 24 by 24 CSS pixels.
- **Meaningful SVG** (a chart, a diagram): put `role="img"` on the `<svg>` and an accessible name from `aria-labelledby` pointing at `<title>` (or at visible text, which MDN prefers when it exists), with `<desc>` for the long description. `role="img"` makes every descendant presentational, so nothing inside, such as a link or a heading, is exposed. Do not rely on animation to convey information.
- **Decorative SVG**: `aria-hidden="true"` and no `<title>` or `<desc>`. Never put `aria-hidden` on something focusable or on an ancestor of something focusable.
- For pages that speak about cystic fibrosis: calm, sober visuals, no flashing, no suggestion of what any person's body or treatment will do, a drawing labelled "schematic" when it is one, and a source and checked date for every scientific caption (leave out any you cannot source).

## Content-Security-Policy

Under `style-src` without `unsafe-inline`, `<style>` elements, `style="..."` attributes and `setAttribute('style', ...)` are blocked, while setting a property directly (`element.style.opacity = '0.5'`) is not. Prefer classes in an external stylesheet and toggle them. Nothing read says how SMIL attributes behave under a strict policy, so test it. The examples inline their CSS and script only so each file runs on its own.

## Verify it

`examples/line-draw.html` reports its state in a `probe` element. `python scripts/test-examples.py` runs it in headless Chromium through the verifier in `webgl-threejs-graphics/scripts/check-webgl.py`, once normally and once with `--reduced-motion`, and checks that one animation runs normally, none runs under reduced motion, the line is drawn either way, and the image has a name. The same verifier checks any local page: a probe element, console errors, and a non-blank screenshot. Use `document.getAnimations()` for deterministic checks of CSS and WAAPI animation; SMIL needs its own (`animationsPaused()`). For flows (keyboard, request logs) use Playwright.

## Tooling

- Run illustrations through SVGO to strip editor cruft, then check the output still has the `id`s, `viewBox`, `<title>` and `<desc>` you need; behaviour depends on the SVGO version and configuration.
- Keep the editable source `.svg` beside the optimized one.

## Sources (read 2026-10-05 through a summarising fetch tool; re-read before quoting)

- MDN, Web Animations API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Using_the_Web_Animations_API
- MDN, CSS animations: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animations/Using_CSS_animations
- MDN, SVG `animate`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/animate and `pauseAnimations`: https://developer.mozilla.org/en-US/docs/Web/API/SVGSVGElement/pauseAnimations
- W3C, SVG 2 changes: https://www.w3.org/TR/SVG2/changes.html
- web.dev, animations guide: https://web.dev/articles/animations-guide
- MDN, `pathLength`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/pathLength
- MDN, `use` and `symbol`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/use
- MDN, `role="img"`: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/img_role
- MDN, `title`: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/title
- MDN, `aria-hidden`: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-hidden
- MDN, `prefers-reduced-motion`: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- MDN, CSP `style-src-attr`: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr
- W3C, WCAG 2.2 Understanding pages for 1.1.1, 2.2.2, 2.3.1 and 2.3.3: https://www.w3.org/WAI/WCAG22/Understanding/

Not found in any source read, so not claimed: the cost of SVG filters, which SVG attributes are cheap to animate, and how SMIL behaves under a strict Content-Security-Policy.
