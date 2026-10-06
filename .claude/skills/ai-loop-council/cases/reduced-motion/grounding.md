# Grounding: prefers-reduced-motion

Primary sources, fetched 2026-09-30. Follow these over your own assumptions.

## MDN: prefers-reduced-motion
https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion

- "detects if a user has enabled a setting on their device to minimize the amount of non-essential motion."
- `reduce`: "Indicates that a user has enabled the setting on their device for reduced motion."
- "`@media (prefers-reduced-motion)` is equivalent to `@media (prefers-reduced-motion: reduce)`." The short form counts as a reduce block.
- MDN's example tones motion down inside the reduce block (`animation: dissolve 4s linear infinite both;`) rather than removing it.

## WCAG 2.2, SC 2.3.3 Animation from Interactions (AAA)
https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html

- "Motion animation triggered by interaction can be disabled, unless the animation is essential to the functionality or the information being conveyed."

## How this case relates
The check enforces a project convention that is stricter than MDN: inside reduce blocks, motion properties must be `none`. MDN-style replacement animations are flagged for human review, not treated as standard violations.
