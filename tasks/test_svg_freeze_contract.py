#!/usr/bin/env python3
"""tasks/test_svg_freeze_contract.py - Deterministic SVG/WebGL2 ?t=SECONDS Visual Visibility & Mobile Zero-Overflow Verifier.

Implements Task T-0226:
Automated verification suite ensuring strict compliance across SVG and WebGL2 visual assets:
1. SVG Frozen Contract:
   - Elements with animated paths (.svg-draw-line, stroke-dashoffset) are governed by
     .is-svg-frozen-time rules ensuring stroke-dashoffset: 0 (!important) when frozen.
   - Animated SVGs include WCAG 2.2.2 pause/resume buttons (data-svg-target, aria-controls,
     or .bench-anim-toggle-btn).
2. WebGL2 Context & Shader Parameters:
   - WebGL2 canvas scripts inspect URLSearchParams for 't' and support deterministic time freezing.
   - Event listeners for webglcontextlost (calling preventDefault) and webglcontextrestored are attached.
   - Headless test fallback (e.g. 2D context or fallback container) is provided.
3. Mobile Layout Budget:
   - CSS rules for parameter controls, cards, and slider groups contain mobile media/container
     queries (@media (max-width: 640px)) enforcing grid-template-columns: 1fr and min-width: 0.

Standard library only. Zero external network calls.
Run:
    python -m unittest tasks/test_svg_freeze_contract.py
    python tasks/test_svg_freeze_contract.py
"""
from __future__ import annotations

import argparse
import re
import sys
import unittest
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# Comment Strippers
# -----------------------------------------------------------------------------

def strip_css_comments(text: str) -> str:
    """Remove CSS /* ... */ comments to prevent false pattern matches."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def strip_js_comments(text: str) -> str:
    """Remove JavaScript multi-line and single-line comments."""
    no_multi = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*$", "", no_multi, flags=re.MULTILINE)


# -----------------------------------------------------------------------------
# Core Verification Logic
# -----------------------------------------------------------------------------

def verify_svg_frozen_contract(html_text: str, css_text: str) -> List[str]:
    """Verify that animated SVGs follow the frozen time visibility and WCAG pause contracts.

    Returns a list of violation messages (empty if compliant).
    """
    errors: List[str] = []
    clean_css = strip_css_comments(css_text)

    # 1. Stroke dash contract:
    # If animated drawing paths exist (e.g. stroke-dashoffset: 1 or .svg-draw-line),
    # there must be a .is-svg-frozen-time override ensuring lines are drawn (stroke-dashoffset: 0).
    has_dash_anim = bool(
        re.search(r"stroke-dashoffset\s*:\s*[1-9]", clean_css)
        or re.search(r"\.svg-draw-line|\.delivery-anim-path|\.aav-splice-path", clean_css)
    )

    if has_dash_anim:
        if ".is-svg-frozen-time" not in clean_css:
            errors.append("CSS missing '.is-svg-frozen-time' contract for animated SVG paths")
        else:
            frozen_blocks = re.findall(
                r"\.is-svg-frozen-time[^{]*\{([^}]+)\}", clean_css, re.DOTALL
            )
            has_drawn_override = any(
                bool(re.search(r"stroke-dashoffset\s*:\s*0", block))
                for block in frozen_blocks
            )
            if not has_drawn_override:
                errors.append(
                    "'.is-svg-frozen-time' block does not enforce 'stroke-dashoffset: 0' for visible lines"
                )

    # 2. WCAG 2.2.2 Pause/Resume button check:
    # Any animated SVG in the HTML must have an associated pause/resume button
    has_animated_svg = bool(
        re.search(r"<svg[^>]*class=[\"'][^\"']*(?:anim|draw|pulse|kinetics)[^\"']*[\"']", html_text, re.I)
        or re.search(r"class=[\"'][^\"']*(?:svg-draw-line|delivery-anim-path|aav-splice-path)[^\"']*[\"']", html_text, re.I)
    )

    if has_animated_svg:
        has_pause_button = bool(
            re.search(r"<button[^>]*data-svg-target=[\"'][^\"']+[\"']", html_text, re.I)
            or re.search(r"<button[^>]*aria-controls=[\"'][^\"']+[\"']", html_text, re.I)
            or re.search(r"<button[^>]*class=[\"'][^\"']*(?:bench-anim-toggle-btn|redosing-anim-btn)[^\"']*[\"']", html_text, re.I)
            or re.search(r"id=[\"'](?:aav-anim-toggle|redosing-anim-toggle|mucin-sim-pause)[\"']", html_text, re.I)
        )
        if not has_pause_button:
            errors.append(
                "Animated SVG markup lacks WCAG 2.2.2 pause/resume button with data-svg-target, aria-controls, or toggle class"
            )

    return errors


def verify_webgl2_script_contract(js_text: str) -> List[str]:
    """Verify that a WebGL2 canvas script follows the deterministic ?t=SECONDS and resilience contract.

    Returns a list of violation messages (empty if compliant).
    """
    errors: List[str] = []
    clean_js = strip_js_comments(js_text)

    # Detect if script initializes WebGL2
    is_webgl2 = "getContext('webgl2')" in clean_js or 'getContext("webgl2")' in clean_js
    if not is_webgl2:
        return errors

    # 1. URLSearchParams ?t=SECONDS time freeze inspection
    has_time_param = bool(
        re.search(r"URLSearchParams\s*\(\s*(?:window\.)?location\.search\s*\)", clean_js)
        and (
            re.search(r"\.get\s*\(\s*['\"]t['\"]\s*\)", clean_js)
            or re.search(r"\.has\s*\(\s*['\"]t['\"]\s*\)", clean_js)
        )
    )
    if not has_time_param:
        errors.append(
            "WebGL2 script does not inspect URLSearchParams(location.search) for 't' parameter"
        )

    # 2. webglcontextlost with preventDefault
    has_context_lost = "webglcontextlost" in clean_js
    if not has_context_lost:
        errors.append("WebGL2 script missing 'webglcontextlost' event listener")
    elif "preventDefault" not in clean_js:
        errors.append(
            "'webglcontextlost' listener does not invoke preventDefault() to allow context restoration"
        )

    # 3. webglcontextrestored listener
    has_context_restored = "webglcontextrestored" in clean_js
    if not has_context_restored:
        errors.append("WebGL2 script missing 'webglcontextrestored' event listener")

    # 4. Headless test / unsupported fallback
    has_fallback = bool(
        "getContext('2d')" in clean_js
        or 'getContext("2d")' in clean_js
        or "fallback" in clean_js.lower()
        or "2d-fallback" in clean_js
    )
    if not has_fallback:
        errors.append(
            "WebGL2 script does not provide graceful 2D context or container fallback for headless environments"
        )

    return errors


def verify_mobile_layout_budget(css_text: str) -> List[str]:
    """Verify that responsive grid/slider layouts collapse to single-column with min-width: 0 on mobile (< 640px).

    Returns a list of violation messages (empty if compliant).
    """
    errors: List[str] = []
    clean_css = strip_css_comments(css_text)

    # Check for targets like .tool-section, .cards-grid, .slider-group, .controls-grid
    target_selectors = [
        r"\.tool-section",
        r"\.cards-grid",
        r"\.slider-group",
        r"\.controls-grid",
        r"\.workbench-cards-grid",
        r"\.ai-bench-kpi-row",
    ]

    matched_selectors = [sel for sel in target_selectors if re.search(sel, clean_css)]
    if not matched_selectors:
        return errors

    # Must contain a mobile query <= 640px
    has_mobile_query = bool(
        re.search(r"@media\s*\(\s*max-width\s*:\s*(?:640px|420px)\s*\)", clean_css)
        or re.search(r"@container[^(]*\(\s*max-width\s*:\s*640px\s*\)", clean_css)
    )
    if not has_mobile_query:
        errors.append("CSS declares multi-column responsive grids but lacks @media (max-width: 640px) block")
        return errors

    # Mobile block must collapse to single column (1fr)
    has_single_col = bool(
        re.search(r"grid-template-columns\s*:\s*1fr", clean_css)
        or re.search(r"grid-template-columns\s*:\s*repeat\(\s*1\s*,\s*minmax\(\s*0\s*,\s*1fr\s*\)\)", clean_css)
    )
    if not has_single_col:
        errors.append(
            "Mobile query does not enforce single-column collapse ('grid-template-columns: 1fr')"
        )

    # Must enforce min-width: 0 on grid items to prevent horizontal overflow on 375px viewports
    has_min_width_zero = bool(
        re.search(r"min-width\s*:\s*0", clean_css)
        or re.search(r"minmax\(\s*0\s*,", clean_css)
    )
    if not has_min_width_zero:
        errors.append(
            "Mobile layout budget missing 'min-width: 0' rule to prevent horizontal clipping"
        )

    return errors


def find_ai_repo_dir(base_root: Optional[Path] = None) -> Optional[Path]:
    """Find the sibling .ai website repository."""
    root = (base_root or REPO_ROOT).resolve()
    candidates = [
        root.parent / ".ai",
        root.parent.parent / ".ai",
        root.parent.parent.parent / ".ai",
        Path("C:/senseiewok/repos/.ai"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "src").is_dir():
            return c.resolve()
    return None


def audit_live_site_assets(ai_dir: Path) -> List[str]:
    """Run verification against actual .ai repository assets."""
    all_errors: List[str] = []
    src = ai_dir / "src"
    if not src.is_dir():
        return [f"Source directory not found at {src}"]

    # 1. Audit CSS contracts
    for css_file in src.glob("*.css"):
        css_text = css_file.read_text(encoding="utf-8", errors="ignore")
        if any(k in css_file.name for k in ["styles-library.css", "styles.css"]):
            errs = verify_mobile_layout_budget(css_text)
            for e in errs:
                all_errors.append(f"{css_file.name}: {e}")

    # 2. Audit SVG frozen contracts across HTML + stylesheets
    library_css = (src / "styles-library.css").read_text(encoding="utf-8", errors="ignore") if (src / "styles-library.css").exists() else ""
    delivery_css = (src / "styles-delivery.css").read_text(encoding="utf-8", errors="ignore") if (src / "styles-delivery.css").exists() else ""
    combined_css = library_css + "\n" + delivery_css

    for html_file in src.rglob("*.html"):
        html_text = html_file.read_text(encoding="utf-8", errors="ignore")
        if "<svg" in html_text and any(k in html_text for k in ["anim", "draw", "pulse", "kinetics"]):
            errs = verify_svg_frozen_contract(html_text, combined_css)
            for e in errs:
                all_errors.append(f"{html_file.relative_to(src)}: {e}")

    # 3. Audit WebGL2 scripts & shared canvas controller
    # WebGL2 resilience (webglcontextlost/restored, fallback) is in cftr-viewer.js,
    # and deterministic ?t=SECONDS parameterization is wired globally in site.js & delivery-view.js.
    cftr_viewer = src / "scripts" / "cftr-viewer.js"
    site_js = src / "scripts" / "site.js"

    if cftr_viewer.exists():
        viewer_text = strip_js_comments(cftr_viewer.read_text(encoding="utf-8", errors="ignore"))
        if "webglcontextlost" not in viewer_text or "preventDefault" not in viewer_text:
            all_errors.append("cftr-viewer.js missing webglcontextlost preventDefault handler")
        if "webglcontextrestored" not in viewer_text:
            all_errors.append("cftr-viewer.js missing webglcontextrestored listener")
        if "fallback" not in viewer_text.lower():
            all_errors.append("cftr-viewer.js missing canvas fallback handler")

    if site_js.exists():
        site_text = strip_js_comments(site_js.read_text(encoding="utf-8", errors="ignore"))
        if "URLSearchParams" not in site_text or "is-svg-frozen-time" not in site_text:
            all_errors.append("site.js missing URLSearchParams ?t=SECONDS frozen time controller")

    return all_errors


# -----------------------------------------------------------------------------
# Unit Tests
# -----------------------------------------------------------------------------

class TestSvgFrozenContractUnit(unittest.TestCase):
    """Unit tests for SVG frozen time visibility and WCAG pause contracts."""

    def test_valid_frozen_contract_passes(self) -> None:
        html = """
        <figure class="viz-card">
          <svg class="delivery-anim-path" width="400" height="200">
            <path class="svg-draw-line" d="M10 80 Q 95 10 180 80" />
          </svg>
          <button type="button" class="bench-anim-toggle-btn" aria-controls="delivery-svg">Pause Animation</button>
        </figure>
        """
        css = """
        .svg-draw-line {
          stroke-dasharray: 1;
          stroke-dashoffset: 1;
          animation: draw 2s ease forwards;
        }
        .is-svg-frozen-time .svg-draw-line {
          stroke-dashoffset: 0 !important;
          animation-play-state: paused !important;
        }
        """
        errors = verify_svg_frozen_contract(html, css)
        self.assertEqual(errors, [])

    def test_missing_frozen_time_override_fails(self) -> None:
        html = """
        <svg class="delivery-anim-path">
          <path class="svg-draw-line" />
        </svg>
        <button type="button" class="bench-anim-toggle-btn">Pause</button>
        """
        css = """
        .svg-draw-line { stroke-dashoffset: 1; animation: draw 2s ease; }
        """
        errors = verify_svg_frozen_contract(html, css)
        self.assertTrue(any(".is-svg-frozen-time" in e for e in errors))

    def test_frozen_time_missing_zero_offset_fails(self) -> None:
        html = """
        <svg class="delivery-anim-path"><path class="svg-draw-line" /></svg>
        <button type="button" class="bench-anim-toggle-btn">Pause</button>
        """
        css = """
        .svg-draw-line { stroke-dashoffset: 1; }
        .is-svg-frozen-time .svg-draw-line {
          opacity: 0.8;
        }
        """
        errors = verify_svg_frozen_contract(html, css)
        self.assertTrue(any("stroke-dashoffset: 0" in e for e in errors))

    def test_missing_pause_button_fails_wcag(self) -> None:
        html = """
        <figure>
          <svg class="delivery-anim-path">
            <path class="svg-draw-line" />
          </svg>
        </figure>
        """
        css = """
        .is-svg-frozen-time .svg-draw-line { stroke-dashoffset: 0 !important; }
        """
        errors = verify_svg_frozen_contract(html, css)
        self.assertTrue(any("pause/resume button" in e for e in errors))


class TestWebGL2ContractUnit(unittest.TestCase):
    """Unit tests for WebGL2 ?t=SECONDS parameterization and context loss recovery."""

    def test_valid_webgl2_script_passes(self) -> None:
        js = """
        function initCanvas(canvas) {
          const gl = canvas.getContext('webgl2');
          if (!gl) {
            canvas.dataset.rendererMode = '2d-fallback';
            const ctx = canvas.getContext('2d');
            return renderFallback(ctx);
          }
          const params = new URLSearchParams(window.location.search);
          const tParam = params.get('t');
          const frozenTime = tParam !== null ? parseFloat(tParam) : null;

          canvas.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            cancelAnimationFrame(rafId);
          });
          canvas.addEventListener('webglcontextrestored', () => {
            initResources();
          });
        }
        """
        errors = verify_webgl2_script_contract(js)
        self.assertEqual(errors, [])

    def test_missing_time_param_fails(self) -> None:
        js = """
        const gl = canvas.getContext('webgl2');
        canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); });
        canvas.addEventListener('webglcontextrestored', () => {});
        const ctx = canvas.getContext('2d');
        """
        errors = verify_webgl2_script_contract(js)
        self.assertTrue(any("URLSearchParams" in e and "'t'" in e for e in errors))

    def test_missing_context_loss_listener_fails(self) -> None:
        js = """
        const gl = canvas.getContext('webgl2');
        const params = new URLSearchParams(location.search);
        const t = params.get('t');
        const fallback = canvas.getContext('2d');
        """
        errors = verify_webgl2_script_contract(js)
        self.assertTrue(any("webglcontextlost" in e for e in errors))

    def test_missing_prevent_default_fails(self) -> None:
        js = """
        const gl = canvas.getContext('webgl2');
        const params = new URLSearchParams(location.search);
        const t = params.get('t');
        canvas.addEventListener('webglcontextlost', (e) => {
          console.log('lost');
        });
        canvas.addEventListener('webglcontextrestored', () => {});
        const ctx = canvas.getContext('2d');
        """
        errors = verify_webgl2_script_contract(js)
        self.assertTrue(any("preventDefault()" in e for e in errors))

    def test_missing_fallback_fails(self) -> None:
        js = """
        const gl = canvas.getContext('webgl2');
        const params = new URLSearchParams(location.search);
        const t = params.get('t');
        canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); });
        canvas.addEventListener('webglcontextrestored', () => {});
        """
        errors = verify_webgl2_script_contract(js)
        self.assertTrue(any("fallback" in e.lower() for e in errors))


class TestMobileLayoutBudgetUnit(unittest.TestCase):
    """Unit tests for 640px / 375px zero-overflow layout budgets."""

    def test_valid_responsive_grid_passes(self) -> None:
        css = """
        .cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 1rem;
        }
        .cards-grid > * {
          min-width: 0;
        }
        @media (max-width: 640px) {
          .cards-grid {
            grid-template-columns: 1fr;
          }
        }
        """
        errors = verify_mobile_layout_budget(css)
        self.assertEqual(errors, [])

    def test_missing_640px_query_fails(self) -> None:
        css = """
        .slider-group {
          display: grid;
          grid-template-columns: 1fr 1fr;
          min-width: 0;
        }
        """
        errors = verify_mobile_layout_budget(css)
        self.assertTrue(any("max-width: 640px" in e for e in errors))

    def test_missing_min_width_zero_fails(self) -> None:
        css = """
        .tool-section {
          display: grid;
          grid-template-columns: 1fr 1fr;
        }
        @media (max-width: 640px) {
          .tool-section {
            grid-template-columns: 1fr;
          }
        }
        """
        errors = verify_mobile_layout_budget(css)
        self.assertTrue(any("min-width: 0" in e for e in errors))


class TestLiveAiAssetsContract(unittest.TestCase):
    """Integration test verifying compliance across .ai repository assets."""

    def test_live_site_assets_pass_contract(self) -> None:
        ai_dir = find_ai_repo_dir(REPO_ROOT)
        if ai_dir is None:
            self.skipTest("Sibling .ai repository not found; skipping live assets verification")

        errors = audit_live_site_assets(ai_dir)
        self.assertEqual(
            errors,
            [],
            f"Found {len(errors)} visual contract violation(s) in .ai:\n" + "\n".join(errors),
        )


# -----------------------------------------------------------------------------
# Main CLI
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic SVG/WebGL2 & Mobile Layout Verifier")
    parser.add_argument("--check", action="store_true", help="Audit live .ai repository assets")
    args, unknown = parser.parse_known_args()

    if args.check:
        ai_dir = find_ai_repo_dir(REPO_ROOT)
        if ai_dir is None:
            print("SKIPPED: Sibling .ai repository not found.")
            return 0
        errors = audit_live_site_assets(ai_dir)
        if errors:
            print(f"CHECK FAIL: {len(errors)} violation(s) detected:")
            for e in errors:
                print(f"  - {e}")
            return 1
        print("CHECK PASS: All SVG frozen contracts, WebGL2 scripts, and mobile layout budgets verified.")
        return 0

    # Delegate to unittest runner
    sys.argv = [sys.argv[0]] + unknown
    unittest.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
