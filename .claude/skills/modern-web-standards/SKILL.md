---
name: modern-web-standards
description: "Engineering guide for high-performance zero-build web applications using modern web standards: semantic HTML5, CSS Grid/Subgrid, Container Queries, native CSS Nesting, Web Components, and strict accessibility budgets."
license: CC0-1.0
compatibility: Works with any Agent-Skills-spec-compatible tool (Claude Code, GitHub Copilot, Qwen3-Coder, Cursor, Antigravity, etc.)
---

# Modern web standards

This skill codifies production engineering practices for building resilient, zero-build web platforms that run natively on modern web standards (HTML5, modern CSS, native JavaScript modules) without frameworks, node_modules dependencies, or bundler build steps.

## 1. Zero-build philosophy & core constraints

Modern browser engines (Chromium, Gecko, WebKit) implement standards that render heavy build pipelines (Webpack, Vite, Babel) unnecessary for public-facing informational, research, and data visualization platforms.

| Dimension | Standard Web Architecture | Framework SPA/SSR Tax |
| :--- | :--- | :--- |
| **Build Step** | Zero build on host; source is served directly. | Continuous CI build steps, lockfile churn, node_modules bloat. |
| **Supply Chain** | Zero external runtime dependencies; immune to npm supply-chain compromises. | Hundreds of transitive dependencies requiring constant vulnerability remediation. |
| **First Contentful Paint (FCP)** | Instant (<100ms); static HTML served directly over HTTP/2 or HTTP/3. | Delayed by client runtime execution, bundle downloads, or SSR hydration lag. |
| **Layout Shift (CLS)** | Deterministic zero shift (`CLS = 0`) using aspect ratios and system font preloads. | Hydration mismatches and late component mounting causing visual jumping. |
| **CSP Compliance** | Strict Content Security Policy without `unsafe-eval` or `unsafe-inline`. | Often requires relaxations for runtime style injection or dynamic evaluation. |

---

## 2. Modern CSS architecture

### CSS Grid & Widescreen canvas utilization

Avoid constraining data-dense or interactive scientific content to narrow single-column mobile viewports on desktop displays. Use modern CSS Grid with responsive `auto-fit` and `minmax()`:

```css
/* Responsive multi-column grid that automatically adapts to widescreen canvases */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.25rem;
  width: min(100% - 2rem, var(--wide, 84rem));
  margin-inline: auto;
}

/* Subgrid for aligning card headers, bodies, and footers across rows */
.dashboard-card {
  display: grid;
  grid-template-rows: subgrid;
  grid-row: span 3;
}

### Mobile (375px) zero-overflow & slider grid rule

Multi-column parameter controls, sliders, or metrics panels (`.tool-grid`, `.slider-group`, `.cards-grid`) must adapt gracefully to narrow mobile devices (down to 375px viewport width, satisfying WCAG 1.4.10 Reflow without horizontal scrollbars):
- Below 640px viewport width, collapse multi-column slider layouts to a single column (`grid-template-columns: 1fr`).
- Always apply `min-width: 0` to CSS Grid and Flexbox children; by default, grid items have `min-width: auto`, which prevents children with wide inputs or code blocks from shrinking and causes horizontal clipping:

```css
/* Multi-column desktop parameter/slider controls */
.controls-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

/* Crucial: allow grid children to shrink below content intrinsic minimum */
.controls-grid > * {
  min-width: 0;
}

/* Narrow mobile viewport collapse (< 640px down to 375px) */
@media (max-width: 640px) {
  .controls-grid {
    grid-template-columns: 1fr;
  }

  .slider-row {
    flex-direction: column;
    align-items: stretch;
  }
}
- **Automated Verification**: Enforced via `tasks/test_svg_freeze_contract.py`, verifying that responsive multi-column control layouts implement `@media (max-width: 640px)` with `grid-template-columns: 1fr` and `min-width: 0`.

### CSS Container Queries (`@container`)

Decouple component styling from the global viewport. Container queries allow components to adapt based on the size of their parent container:

```css
/* Define the containment context */
.card-wrapper {
  container-type: inline-size;
  container-name: card-container;
}

/* Component adapts when placed in a wide container */
@container card-container (min-width: 480px) {
  .research-card {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
  }
}
```

### Native CSS nesting & modern color spaces

Use native CSS nesting without preprocessors (Sass/Less) and leverage `color-mix()` in perceptual color spaces (`oklab`):

```css
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border-glass);

  /* Native nesting */
  &:hover {
    border-color: color-mix(in oklab, var(--neon-cyan) 60%, transparent);
    box-shadow: 0 4px 20px color-mix(in oklab, var(--neon-cyan) 10%, transparent);
  }

  & .card-title {
    font-size: 1.1rem;
    color: var(--ink-primary);
  }
}
```

---

## 3. Web Components & Custom Elements

For reusable interactive widgets (such as coordinate viewers, sliders, or research filters), use autonomous Custom Elements without shadow DOM overhead when global styling applies:

```javascript
// Native autonomous custom element using Light DOM for seamless styling
export class BiophysicsCard extends HTMLElement {
  static get observedAttributes() {
    return ['track', 'task-id'];
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this.render();
    }
  }

  render() {
    const track = this.getAttribute('track') || 'Track A';
    const taskId = this.getAttribute('task-id') || '';
    
    // Declarative, safe DOM generation
    this.innerHTML = `
      <div class="card-inner">
        <span class="card-badge">${track}</span>
        <span class="card-task">${taskId}</span>
        <slot></slot>
      </div>
    `;
  }
}

if (!customElements.get('biophysics-card')) {
  customElements.define('biophysics-card', BiophysicsCard);
}
```

---

## 4. Accessibility & Dignity Guidelines

Every public interface must meet strict accessibility standards:

1. **Semantic DOM Hierarchy**: Exactly one `<h1>` per page. Heading levels (`<h2>` to `<h6>`) must never skip ranks.
2. **Keyboard Navigation**:
   - All interactive controls (`button`, `a`, `input`) must have distinct `:focus-visible` outlines.
   - Never remove outlines without providing a high-contrast replacement.
   - Target sizes must measure at least `44x44px` on touch screens.
3. **Motion Hygiene**:
   - Always honor `prefers-reduced-motion`:
     ```css
     @media (prefers-reduced-motion: reduce) {
       *, *::before, *::after {
         animation-duration: 0.01ms !important;
         animation-iteration-count: 1 !important;
         transition-duration: 0.01ms !important;
         scroll-behavior: auto !important;
       }
     }
     ```
4. **Color Contrast**:
   - Body text against background must maintain a contrast ratio of at least `4.5:1` (WCAG AA).
   - Large text (≥ 18pt or 14pt bold) must maintain at least `3:1`.
5. **Screen Reader Support**:
   - Hidden structural labels use the standard utility:
     ```css
     .visually-hidden {
       position: absolute;
       width: 1px;
       height: 1px;
       padding: 0;
       margin: -1px;
       overflow: hidden;
       clip: rect(0, 0, 0, 0);
       white-space: nowrap;
       border: 0;
     }
     ```

---

## 5. Verification & Performance Budgets

Deterministic automated tests should assert frontend invariants:

- **Page weight budgets**: Assert uncompressed and served bytes for HTML, CSS, and JS (e.g., `styles.css < 80 KB`).
- **Header & Mobile layout budgets**: Assert that headers do not exceed vertical pixel budgets (e.g., `headerBottom <= 300px` with banner, `<= 170px` without banner on 360px viewports).
- **Broken link & fragment detection**: Verify all in-page jump links (`href="#section"`) resolve to matching `id` attributes in the DOM.
