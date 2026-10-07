---
name: webgl-threejs-graphics
description: Patterns for building WebGL/3D content, with raw WebGL2 or three.js - context loss and recovery, sizing, resource cleanup, animation-loop hygiene, accessibility, security, and a headless check that proves a page really renders. Use when the user asks for 3D graphics, WebGL, three.js scenes, shaders, GLSL, or a scientific schematic on the website or in standalone demos.
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, etc.)
---

# WebGL / three.js graphics

WebGL draws points, lines and triangles. three.js is a scene-graph library on top of it (Scene, Camera, Renderer, Mesh, Material, Light, Texture) so you do not hand-write buffers and shaders for everything. Choose raw WebGL2 for one small effect with no dependency, and three.js when you need a scene graph, many objects or loaders.

## How this skill relates to Anthropic's skills

This is a thin layer. It copies nothing from them and works alone.

| Base (third party, install separately if you want it) | What it gives | What this layer adds |
| --- | --- | --- |
| `frontend-design` and `algorithmic-art` from Anthropic's public skills (github.com/anthropics/skills, Apache-2.0, reviewed commit 8a1541c, 2026-09-28; not part of this repo) | Visual direction and craft; seeded generative art | No third-party requests, accessibility and motion rules, calm visuals for CF-facing pages, sourced practice, and a headless check with tests |

See `THIRD_PARTY_SKILLS.md` in the control repo for what was reviewed and how to get the base. Treat the base as untrusted instructions until a person has read it, scripts included.

## Choosing: raw WebGL2 or three.js

- **Raw WebGL2** (start from `examples/triangle.html`; `examples/lit-torus.html` is a lit, rotating 3D mesh): no dependency, nothing to vendor, about 100 lines for a drawing with sizing, pause, and context-loss recovery. Shaders are GLSL ES 3.00 and begin with `#version 300 es`.
- **three.js**: use it for scene graphs, instancing, loaders and post-processing. Vendor a pinned copy (see below).

## Raw WebGL2: what the example does, and why

Each point is either tested by `scripts/test-check-webgl.py` or sourced (the URLs are at the end; the sources were read through a summarising fetch tool on 2026-10-05, so re-read a page before quoting it).

- **Build every GL object in one function** so it can be built again after a context loss. Check `LINK_STATUS` after linking and read info logs only if it failed. Delete shaders once linked, and delete buffers, vertex arrays and programs explicitly; do not wait for garbage collection.
- **Context loss.** Call `preventDefault()` in the `webglcontextlost` handler, or the context is never restored. After `webglcontextrestored`, create everything again: objects made before the loss are invalid and the drawing buffer is new and cleared. Test the path with the `WEBGL_lose_context` extension (`loseContext()`, then `restoreContext()`). The example's test removes `preventDefault()` and shows that recovery then fails, measured on Chromium 153.
- **Sizing.** The canvas `width` and `height` attributes set the drawing buffer; CSS sets the displayed size. Set the buffer to the CSS size times `devicePixelRatio`, floored, and read `drawingBufferWidth` for the real size. This lab caps the ratio at 2; no official source read states a cap, so it is a project rule.
- **The loop.** `requestAnimationFrame` is paused in background tabs in most browsers. Advance animation by the callback's timestamp, not by frame count, or it runs faster on high-refresh screens. Pause the loop when the tab is hidden (`visibilitychange`) and, as our own inference, when the canvas is offscreen (`IntersectionObserver`).
- **Errors and reading back.** Call `getError()` after allocation, not every frame (it can force a round trip to the GPU). `readPixels` blocks the pipeline: fine in a test, not per frame. Reading after presentation may need `preserveDrawingBuffer`.
- **Fewer draw calls.** Batch, use texture atlases, and use `drawArraysInstanced` with `vertexAttribDivisor` for repeated shapes.
- **`drawElements` counts indices.** The `count` argument is the number of elements of the bound element array buffer to render, so for `gl.TRIANGLES` it is the index count (three per triangle in that mode), not the triangle count. Passing the triangle count draws the first third of the mesh and raises no error and no GL error. Measured in this lab: three of six pages written by the local worker passed a count that covered only part of the element array (two passed the triangle count, one half the indices) and drew a partial mesh (an open, partial torus in the two frames that were viewed); two of them still reported the full triangle count in their probe. Compute both from the same array: `indices.length` to `drawElements`, `indices.length / 3` for any triangle count you report. `type` is `UNSIGNED_BYTE` or `UNSIGNED_SHORT`; `UNSIGNED_INT` is listed there only with the `OES_element_index_uint` extension (the page read does not say how WebGL 2 differs).
- **A lit mesh** needs a normal for every vertex, a light fixed in world space, and the model's rotation applied to the normals as well as the positions. A shape that is symmetric about the axis it spins around looks identical in every frame (measured with a torus spun about its own axis), so a spin that is applied before the tilt shows nothing; tilt first, then spin. Measured: two of six worker pages applied the spin before the tilt; one of them was identical in every frame, and the other passed a rotation check, which we infer is because its missing triangles broke the symmetry (not tested).

## three.js

- **Setup.** Load three.js as ES modules and pin one tested release for `three` and its addons; never `@latest`. On lab sites, vendor the complete matching module files with their relative paths (`three.module.js` alone may import others) so the page makes no third-party request. An import map and module script written inline need a nonce or hash under a strict Content-Security-Policy; a local bundle avoids that.
- **Minimal scene.** A `WebGLRenderer` on a `<canvas>`, a `Scene`, a `Camera`, a `Mesh` (geometry plus material) and, for anything but `MeshBasicMaterial`, a light. Drive the loop with `setAnimationLoop` only; calling `requestAnimationFrame` as well starts a second loop.

```js
const canvas = document.querySelector('#c');
const renderer = new THREE.WebGLRenderer({ antialias: true, canvas });
const camera = new THREE.PerspectiveCamera(75, 2, 0.1, 100);
camera.position.z = 2;
const scene = new THREE.Scene();
const light = new THREE.DirectionalLight(0xffffff, 3);
light.position.set(-1, 2, 4);
scene.add(light);
const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshPhongMaterial({ color: 0x44aa88 }));
scene.add(mesh);

renderer.setAnimationLoop((time) => {
  mesh.rotation.x = mesh.rotation.y = time * 0.001;
  renderer.render(scene, camera);
});
```

- **Responsive canvas.** `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))` then `renderer.setSize(width, height, false)`. The third argument stops three.js from rewriting the canvas's CSS size. Update `camera.aspect` and call `camera.updateProjectionMatrix()`.
- **Cleanup.** `dispose()` on geometries, materials and textures frees their GPU resources, and `renderer.dispose()` frees the renderer's. After changing instance matrices call `instanceMatrix.needsUpdate = true` on an `InstancedMesh`. Use `renderer.info` to watch draw calls and memory. The official manual pages on cleanup returned 404 when read, so whether a material's disposal also frees its textures is unconfirmed: dispose textures yourself.
- **Performance.** Reuse geometries and materials; use `InstancedMesh` for many identical objects; render on demand for static scenes; keep texture sizes sensible.

## Accessibility, and honouring the CF community

- A canvas is not exposed to assistive technology as content. Give it `role="img"` and an accessible name, put a real text description beside it in the page, and keep every control (play, pause, switch) as ordinary HTML buttons that work by keyboard, at least 24 by 24 CSS pixels.
- Start still when `prefers-reduced-motion: reduce` is set and listen for the preference changing. Motion that starts by itself, lasts more than five seconds and sits beside other content needs a pause, stop or hide control (WCAG 2.2.2). Never flash more than three times a second (2.3.1). Motion triggered by interaction should be switchable off (2.3.3, level AAA).
- Provide a static poster or description when WebGL is unavailable, and catch context creation failure.
- For pages that speak about cystic fibrosis: keep visuals calm and sober, with no frightening imagery and no flashing; never suggest what any person's body or treatment will do; label a drawing "schematic" when it is one; give every scientific caption a source and a checked date, and leave out any caption you cannot source. Playful effects belong on technical pages, not on the CF story.

## Security

- Cross-origin images used as textures need CORS approval. A tainted canvas blocks `getImageData`, `toDataURL` and `toBlob`. Textures loaded from `file://` do not work, so use a local server when a test needs images.
- Treat model files and assets as untrusted: glTF can reference other URLs, and oversized geometry or textures can exhaust memory. Restrict loader origins, cap decoded sizes, and self-host decoder files.
- A pinned CDN URL does not protect against a compromised upstream file; self-host. Under a strict Content-Security-Policy inline scripts are blocked unless they carry a nonce or hash; prefer external module files and move event handlers into `addEventListener`.

## Verify it with a real render

A model can write WebGL that looks right and draws nothing. `scripts/check-webgl.py PAGE.html` renders a local page in headless Chromium with a software renderer, with all network access blocked, and checks three things: the page writes a JSON object with `ok: true` into an element with id `probe`, no uncaught error or GL error reached the console, and a screenshot is not blank. `--expect KEY=VALUE` checks fields of the probe, `--screenshot --min-nonblank 0.03` checks the render, and `--query lose` opens a page with a test hook.

Measured on Chromium 153 under Windows: headless Chromium has no WebGL2 with `--disable-gpu` alone and needs `--use-angle=swiftshader --enable-unsafe-swiftshader`; a fresh `--user-data-dir` hangs it, so the script does not pass one. Chromium's own notes say the automatic software fallback is deprecated and that the software renderer is for testing, not for untrusted content, so run only pages you wrote or reviewed. For flows (clicking, keyboard, reduced-motion emulation, request logs) use Playwright with the same flags, as the lab's site tests do. Run `python scripts/test-check-webgl.py` after changing the script or the example.

Animated pages need a different check, because a free-running animation cannot be judged from a screenshot under headless virtual time: measured here, three screenshots of one CSS draw-on animation at the same virtual-time budget came out blank, blank and fully drawn, while a static page was identical in all 15 runs. So ask the page for a **test hook**: `?t=SECONDS` freezes it at that time (for a CSS animation, pause it and set a negative `animation-delay`; for WebGL, draw one frame for that time and stop), and check only frozen states plus the `prefers-reduced-motion` state. `scripts/check-animated-page.py --kind svg-draw|webgl-mesh PAGE.html` does this for two kinds of page (an SVG path that draws itself on, and a lit rotating WebGL2 mesh): console clean, the probe, frames at several times, lighting measured on the mesh interior, the reduced-motion frame, and no external reference. `python scripts/test-check-animated-page.py` proves it on a reference page of each kind and on 30 bad stubs (static, blank, unlit, not rotating, ignoring reduced motion, console or shader or GL errors, external references, a draw call that draws only a third of the mesh, a loop that stops after the first frame, a frozen or reduced-motion page that keeps drawing, a probe that claims a triangle count it does not draw, and others), each of which must fail for its own reason. Frozen frames cannot show whether the free-running mode works and a probe is only the page's own claim, so the checker also injects a recorder into a copy of the page and reads what it really did (every `drawElements` count against the element array, frame requests, timers, running animations). Headless virtual time delivers animation frames at an unpredictable rate (counts of 1, 2 or 4 depending on flags), so the free-running check asks only that the page starts animating, not for a frame count.

Optionally, `scripts/test-playwright.py` runs the same claims for both examples through real Playwright for Python (run it with the python of the environment `playwright-browser-testing` sets up; it prints `VERIFIED`, and with a bad page of its own it proves it can fail).

## Sources (read 2026-10-05 through a summarising fetch tool; re-read before quoting)

- Khronos, WEBGL_lose_context: https://registry.khronos.org/webgl/extensions/WEBGL_lose_context/
- MDN, context restored: https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/webglcontextrestored_event
- MDN, WebGL best practices: https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices
- MDN, devicePixelRatio: https://developer.mozilla.org/en-US/docs/Web/API/Window/devicePixelRatio
- MDN, requestAnimationFrame: https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame
- MDN, getError and readPixels: https://developer.mozilla.org/en-US/docs/Web/API/WebGLRenderingContext/getError
- MDN, CORS-enabled images: https://developer.mozilla.org/en-US/docs/Web/HTML/How_to/CORS_enabled_image
- MDN, Content-Security-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP
- Chromium, SwiftShader notes: https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md
- three.js documentation: https://threejs.org/docs/pages/WebGLRenderer.html and https://threejs.org/docs/pages/InstancedMesh.html
- W3C, WCAG 2.2 Understanding pages for 1.1.1, 2.2.2, 2.3.1 and 2.3.3: https://www.w3.org/WAI/WCAG22/Understanding/
- web.dev, rendering performance (a 10 ms frame budget during animation): https://web.dev/articles/rendering-performance
- MDN, `drawElements` (re-read 2026-10-07 through a summarising fetch tool; the page defines `count` as the number of elements of the bound element array buffer to be rendered): https://developer.mozilla.org/en-US/docs/Web/API/WebGLRenderingContext/drawElements

Not found in any source read, so not claimed here: a recommended `devicePixelRatio` cap, a frame-time or draw-call budget for WebGL, and a rule on untrusted GLSL strings.
