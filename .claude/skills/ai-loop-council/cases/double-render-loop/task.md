Detect three.js code that schedules the same render function twice per frame.

In every `.js` and `.mjs` file (any folder), exit 1 if some function name is both:
- passed to `setAnimationLoop(...)` on any object (e.g. `renderer.setAnimationLoop(render)`), and
- passed to `requestAnimationFrame(...)`, called bare or as `window.`, `globalThis.` or `self.requestAnimationFrame(...)`,

within the same file. Names may be declared as functions or as arrow functions assigned to a variable, and there may be spaces inside the parentheses.

Do not flag:
- `setAnimationLoop(null)`, which stops the loop.
- `requestAnimationFrame` used for a different function than the one given to `setAnimationLoop`.
- A classic manual loop that uses only `requestAnimationFrame`.
- Mentions inside `//` or `/* */` comments.
- A function name used with `setAnimationLoop` in one file and with `requestAnimationFrame` in a different file (separate modules).
JavaScript names are case-sensitive.
