# Grounding: three.js animation loop

Fetched 2026-09-30.

## three.js docs: WebGLRenderer.setAnimationLoop()
https://threejs.org/docs/pages/WebGLRenderer.html

- "Applications are advised to always define the animation loop with this method and not manually with `requestAnimationFrame()` for best compatibility."

`setAnimationLoop(callback)` calls the callback every frame by itself. If the callback also calls `requestAnimationFrame(callback)`, each frame queues one more call, so the scene renders more than once per frame. This bug was found in this workspace's own three.js skill during a council review.
