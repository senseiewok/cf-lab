Detect CSS that turns motion ON for users who asked for reduced motion. This enforces a project convention that is stricter than MDN (see Grounding): flagged lines go to human review.

Flag (exit 1) when, inside any `@media` rule whose condition includes `prefers-reduced-motion: reduce` or the short form `(prefers-reduced-motion)` with no value (they are equivalent), there is an `animation`, `animation-name`, `transition` or `transition-property` declaration whose value is not `none` (ignore `!important` when comparing).

Do not flag (exit 0):
- `animation: none` / `transition: none` inside such a block (that correctly disables motion).
- Duration, delay or iteration longhands such as `animation-duration: 0.01ms` inside such a block (a common way to shorten motion).
- Any animation outside those blocks, including inside `@media (prefers-reduced-motion: no-preference)`.

CSS may be minified, may combine media types (`screen and (...)`), may contain several media blocks, and there may be several `.css` files.
