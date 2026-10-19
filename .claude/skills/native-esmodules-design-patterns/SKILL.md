---
name: native-esmodules-design-patterns
description: "Production-grade software design patterns for native browser ES modules without bundlers: Singleton stores, EventTarget Pub/Sub, Model-View-Presenter (MVP), Repository data sources, and CSP-safe modular architecture."
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, Antigravity, etc.)
---

# Native ES modules & ES6+ design patterns

This skill codifies robust software design patterns for modern JavaScript applications built entirely on native ECMAScript Modules (`<script type="module">`) and modern ES6+ language primitives (Classes, Proxies, Symbols, Generators, Private Fields, and WeakMaps). It provides a zero-build, framework-free foundation for resilient and maintainable web architectures.

---

## 1. Native ES module lifecycle & properties

Native browser ES modules provide runtime guarantees that eliminate the need for bundlers or module loaders:

1. **Singleton Execution**: A module URL is fetched and evaluated exactly once per document lifecycle. Subsequent imports across different files receive the same cached instance.
2. **Strict Mode by Default**: Modules always execute in strict mode (`"use strict"` is automatic).
3. **Lexical Scoping**: Variables declared at module top-level are scoped to the module and never pollute `window` or global scope.
4. **Deferred Execution**: Modules execute in document order after the HTML is parsed, equivalent to `<script defer>`.
5. **CORS Enforcement**: External module scripts require CORS headers (`Access-Control-Allow-Origin`).

---

## 2. Creational patterns in ES6+

### A. Native Module Singleton vs. Private Field Singleton

In ES modules, exporting an instantiated object gives an automatic singleton. For classes that require strict single-instance instantiation:

```javascript
// Native Module Singleton (Recommended)
class AppState extends EventTarget {
  #data = new Map();

  set(key, val) {
    this.#data.set(key, val);
    this.dispatchEvent(new CustomEvent('update', { detail: { key, val } }));
  }

  get(key) {
    return this.#data.get(key);
  }
}

// Single instance shared by all consumers across the document
export const appState = new AppState();
```

### B. Factory Pattern with Computed Property Names & Polymorphism

Use factories to instantiate polymorphic objects based on configuration or registry keys:

```javascript
class ClassIMutation {
  type = 'Nonsense';
  requiresNMDRescue = true;
  constructor(name, residue) { this.name = name; this.residue = residue; }
}

class ClassIIMutation {
  type = 'Misfolding';
  requiresCorrector = true;
  constructor(name, residue) { this.name = name; this.residue = residue; }
}

export class VariantFactory {
  static #registry = {
    'G542X': (res) => new ClassIMutation('G542X', res),
    'W1282X': (res) => new ClassIMutation('W1282X', res),
    'F508del': (res) => new ClassIIMutation('F508del', res),
    'N1303K': (res) => new ClassIIMutation('N1303K', res)
  };

  static create(variantName, residue) {
    const creator = this.#registry[variantName];
    if (!creator) throw new Error(`Unknown variant class: ${variantName}`);
    return creator(residue);
  }
}
```

### C. Fluent Builder Pattern

Method chaining with private state for complex query or coordinate generation:

```javascript
export class CryoEMQueryBuilder {
  #structure = '6MSM';
  #residues = [];
  #distanceCutoff = 5.0;

  forStructure(id) {
    this.#structure = id;
    return this;
  }

  nearResidue(num) {
    this.#residues.push(num);
    return this;
  }

  withinAngstroms(distance) {
    this.#distanceCutoff = distance;
    return this;
  }

  build() {
    return Object.freeze({
      structure: this.#structure,
      residues: [...this.#residues],
      cutoff: this.#distanceCutoff
    });
  }
}
```

---

## 3. Structural patterns in ES6+

### A. Facade Pattern

Hide complex subsystems (such as WebGL2 shaders, camera quaternions, or coordinate parsing) behind a clean, simple public module API:

```javascript
// cftr-facade.js — Hides WebGL complexity from the UI
import { WebGLRenderer } from './webgl-renderer.js';
import { PDBParser } from './pdb-parser.js';

export class CFTRViewerFacade {
  #renderer;
  #canvas;

  constructor(canvasElement) {
    this.#canvas = canvasElement;
    this.#renderer = new WebGLRenderer(this.#canvas);
  }

  async loadStructure(accessionId) {
    const rawData = await fetch(`../data/structures/${accessionId}.bin`);
    const coordinates = PDBParser.parse(await rawData.arrayBuffer());
    this.#renderer.renderMesh(coordinates);
  }

  focusResidue(residueIndex) {
    this.#renderer.animateCameraTo(residueIndex);
  }
}
```

### B. Native `Proxy` & `Reflect` Pattern (Observables & Validation)

Use native JavaScript `Proxy` to intercept object operations for validation, lazy loading, or change notification:

```javascript
export function createObservable(target, onChange) {
  return new Proxy(target, {
    set(obj, prop, value, receiver) {
      const prev = Reflect.get(obj, prop, receiver);
      if (prev !== value) {
        const success = Reflect.set(obj, prop, value, receiver);
        if (success) onChange(prop, value, prev);
        return success;
      }
      return true;
    }
  });
}

// Usage:
const settings = createObservable({ zoom: 1.0, theme: 'dark' }, (prop, val) => {
  console.log(`Setting ${prop} changed to ${val}`);
});
settings.zoom = 1.5; // Logs: Setting zoom changed to 1.5
```

### C. Flyweight Pattern with `WeakMap`

Conserve memory when managing thousands of protein atoms or trial records by caching immutable shared data:

```javascript
const structureCache = new Map();

export class StructureFlyweightFactory {
  static getStructure(id) {
    if (!structureCache.has(id)) {
      structureCache.set(id, Object.freeze({
        id,
        loadedAt: Date.now(),
        meshData: new Float32Array(/* ... */)
      }));
    }
    return structureCache.get(id);
  }
}
```

---

## 4. Behavioral patterns in ES6+

### A. Observer / Pub-Sub via standard `EventTarget`

Zero-dependency event bus using standard DOM event interfaces:

```javascript
// bus.js
export const bus = new EventTarget();

export function emit(eventName, detail = {}) {
  bus.dispatchEvent(new CustomEvent(eventName, { detail }));
}

export function on(eventName, handler) {
  const listener = (event) => handler(event.detail, event);
  bus.addEventListener(eventName, listener);
  return () => bus.removeEventListener(eventName, listener);
}
```

### B. Strategy Pattern with First-Class Functions

In ES6+, objects mapping keys to first-class functions replace heavy object-oriented strategy hierarchies:

```javascript
export const GatingStrategies = {
  wt: (voltage, atp) => 1.0 / (1.0 + Math.exp(-voltage / 25)),
  g542x_rescued: (voltage, atp) => 0.15 * (1.0 / (1.0 + Math.exp(-voltage / 25))),
  potentiated: (voltage, atp) => 0.65 * (1.0 / (1.0 + Math.exp(-voltage / 30)))
};

export function computeOpenProbability(strategyKey, voltage, atp) {
  const strategy = GatingStrategies[strategyKey];
  if (!strategy) throw new Error(`Strategy ${strategyKey} not found`);
  return strategy(voltage, atp);
}
```

### C. Native Iterators & Generators (`Symbol.iterator`)

Implement standard iteration protocols for dataset walking, sequence traversal, and lazy evaluation:

```javascript
export class ProteinSequence {
  #sequence;

  constructor(sequenceString) {
    this.#sequence = sequenceString;
  }

  *[Symbol.iterator]() {
    for (let i = 0; i < this.#sequence.length; i++) {
      yield { index: i + 1, residue: this.#sequence[i] };
    }
  }

  // Window generator for structural motifs
  *windows(size = 3) {
    for (let i = 0; i <= this.#sequence.length - size; i++) {
      yield { start: i + 1, motif: this.#sequence.slice(i, i + size) };
    }
  }
}

// Consumed naturally with for...of or spread:
const seq = new ProteinSequence('MVRP...F508...TR');
for (const { index, residue } of seq) {
  if (index === 508) console.log(`Found ${residue} at 508`);
}
```

---

## 5. Architectural patterns

### A. Model-View-Presenter (MVP) without Virtual DOM

Decouple business logic and raw data from DOM manipulation:

```mermaid
flowchart LR
    Model["Model\n(Immutable Data & Math)"] <--> Presenter["Presenter\n(Coordinates state)"]
    Presenter <--> View["View\n(Passive DOM & Events)"]
```

- **Model**: Pure data structures and coordinate calculations (`cftr-data.js`).
- **View**: Passive DOM elements; captures user events and invokes Presenter callbacks (`cftr-page.js`).
- **Presenter**: Mediates between Model and View, managing active structure selection and camera position.

### B. Repository Pattern for Sourced Evidence

Separate immutable reference facts from UI components:

```javascript
export const EvidenceRepository = {
  #data: Object.freeze({
    STOP2: { nct: 'NCT02781610', participants: 982, pmid: 34469706 },
    DESCHAMP_2023: { pmid: 37598041, cohortSize: 78, pValue: '< 0.001' }
  }),

  get(key) {
    const record = this.#data[key];
    if (!record) throw new Error(`Evidence key ${key} not in catalog`);
    return record;
  }
};
```

---

## 6. CSP-Safe dynamic imports & code splitting

Load heavy visualization modules (such as WebGL2 shaders, 3D engines, or large coordinate maps) only when needed:

```javascript
// Lazy-load 3D viewer only when container scrolls into viewport
export function lazyLoadViewer(containerElement) {
  const observer = new IntersectionObserver((entries, obs) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        obs.disconnect();
        import('./cftr-viewer.js').then(({ initViewer }) => {
          initViewer(containerElement);
        });
      }
    }
  }, { rootMargin: '200px' });

  observer.observe(containerElement);
}
```

---

## 7. Deterministic testing checklist

Verify vanilla ES modules without heavy test frameworks:

- [ ] **Pure Function Isolation**: Math, coordinate transforms, and parsers must have zero DOM dependencies and run cleanly under Python or Node unit tests.
- [ ] **Immutable Records**: Verify that data dictionaries use `Object.freeze()` and throw `TypeError` on attempted mutation in strict mode.
- [ ] **Module Cache Isolation**: Test that module singletons reset state predictably between test runs.
- [ ] **Strict CSP Compliance**: Ensure no `eval()`, `new Function()`, or inline event handler attributes (`onclick`) are emitted. Zero `.innerHTML` across biophysical workbenches.

---

## 8. Zero-`innerHTML` DOM & SVG namespace factory pattern

In strict Content Security Policy environments (`require-trusted-types-for 'script'`, `style-src-attr 'none'`) and clinical biophysical workbenches, assignment to `.innerHTML` or `.outerHTML` is strictly prohibited. Furthermore, creating SVG elements via `.innerHTML` inside an HTML document often defaults elements to the `http://www.w3.org/1999/xhtml` namespace, causing SVG elements (`<circle>`, `<path>`, `<g>`) to fail to render or participate in SVG geometry rendering.

Use pure DOM APIs (`document.createElement`, `document.createElementNS`, and `Element.prototype.replaceChildren()`) through a clean, reusable 15-line helper pattern:

```javascript
const SVG_NS = 'http://www.w3.org/2000/svg';

/** Safe HTML element factory */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'className') node.className = v;
    else if (v !== null && v !== undefined) node.setAttribute(k, String(v));
  }
  node.append(...children.flat().filter(Boolean));
  return node;
}

/** Namespace-safe SVG element factory */
export function svgEl(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== null && v !== undefined) node.setAttribute(k, String(v));
  }
  node.append(...children.flat().filter(Boolean));
  return node;
}

/** Atomic, XSS-proof DOM replacement */
export function mountView(container, ...nodes) {
  container.replaceChildren(...nodes.flat().filter(Boolean));
}
```

---

## 9. `AbortController` (`{ signal }`) listener lifecycle & batched microtask reactivity

### A. Automatic Listener Cleanup with `AbortSignal`

When building interactive workbenches (e.g. parameter sliders, media queries, tab switches), attaching anonymous event listeners without cleanup causes memory leaks and stale event handler execution across page re-renders. Modern `addEventListener` accepts an `AbortSignal`:

```javascript
export class BiophysicsPanel {
  #abort = new AbortController();

  mount(root) {
    const { signal } = this.#abort;

    // Window and document listeners automatically detach when aborted
    window.addEventListener('languagechange', () => this.#onLanguage(), { signal });
    window.matchMedia('(prefers-reduced-motion: reduce)')
      .addEventListener('change', () => this.#onMotionPref(), { signal });

    // Slider inputs with signal lifecycle
    const slider = root.querySelector('#solids-slider');
    slider.addEventListener('input', () => this.#scheduleUpdate(), { signal });
  }

  destroy() {
    // Single call cleanly tears down all bound listeners
    this.#abort.abort();
  }
}
```

### B. Microtask Coalescing (`queueMicrotask`) for High-Frequency Inputs

When users drag range sliders (which fire `input` events at 60–120 Hz), triggering immediate heavy DOM recalculations or WebGL uniform updates per event introduces severe jank. Coalesce events into a single update per event-loop tick using `queueMicrotask`:

```javascript
export class ResponsiveSimulator {
  #pendingUpdate = false;
  #state = { temp: 37.0, conc: 150 };

  updateParam(key, val) {
    this.#state[key] = val;
    if (this.#pendingUpdate) return;

    this.#pendingUpdate = true;
    queueMicrotask(() => {
      this.#pendingUpdate = false;
      this.#render(this.#state); // Executes once per microtask tick
    });
  }

  #render(state) {
    // Recompute biophysical model & redraw SVG/canvas
  }
}
```

---

## 10. Module Web Workers & transferable `Float32Array` buffers

Offload compute-heavy biophysical simulations (such as stiff Runge-Kutta ODE numerical integration of CFTR gating kinetics, Monte Carlo mucin mesh penetration sweeps, or 3D coordinate superpositions) off the main UI thread using native module Web Workers and zero-copy transferable buffers:

```javascript
// main.js - Spawning a module Web Worker with relative URL resolution
export function spawnBiophysicsWorker() {
  const workerUrl = new URL('./biophysics-solver.worker.js', import.meta.url);
  const worker = new Worker(workerUrl, { type: 'module' });

  // Allocate 100,000 particle coordinates (3 coordinates per particle)
  const particleBuffer = new Float32Array(300_000);

  // Send buffer with zero-copy transfer (buffer ownership moves to worker)
  worker.postMessage({ type: 'SOLVE_STEP', dt: 0.01, buffer: particleBuffer }, [particleBuffer.buffer]);

  worker.onmessage = (e) => {
    const { buffer } = e.data;
    // buffer is transferred back without copying; ready for WebGL gl.bufferSubData
    renderGpuCoordinates(buffer);
  };

  return worker;
}
```
