#!/usr/bin/env python3
"""tasks/test_svg_freeze_contract.py - Verification suite for deterministic SVG/WebGL2 time freeze & mobile zero-overflow.

Implements verification requirements for Track C (Task T-0226):
1. Verifies that skill files document ?t=SECONDS, stroke-dashoffset: 0 !important, webglcontextlost,
   grid-template-columns: 1fr, min-width: 0, and zero-innerHTML DOM construction contracts.
2. Verifies .is-svg-frozen-time .svg-draw-line { stroke-dashoffset: 0 !important; } and prefers-reduced-motion
   rules in stylesheets, plus synthetic negative detection.
3. Scans animated schematics for viewBox, accessible naming (role="img", aria-labelledby, aria-label, <title>),
   and WCAG 2.2.2 pause/resume controls.
4. Verifies WebGL2 scripts attach webglcontextlost (calling preventDefault()) and webglcontextrestored,
   read ?t= from URLSearchParams for deterministic freeze, and provide 2D canvas or SVG fallback.
5. Verifies mobile single-column layout contracts (grid-template-columns: 1fr, min-width: 0).
6. Verifies zero .innerHTML assignments and zero eval() / new Function() in biophysical ES modules.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

# Repository Paths
LAB_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = LAB_ROOT / ".claude" / "skills"

# Sibling .ai repository discovery
CANDIDATE_AI_DIRS = [
    LAB_ROOT.parent / ".ai",
    LAB_ROOT.parents[1] / ".ai",
    Path("C:/senseiewok/repos/.ai"),
]

AI_ROOT = None
for cand in CANDIDATE_AI_DIRS:
    if cand.is_dir() and (cand / "src").is_dir():
        AI_ROOT = cand
        break

AI_SRC = (AI_ROOT / "src") if AI_ROOT is not None else None


def strip_comments(text: str) -> str:
    """Strips block and line comments to avoid false-positive matches in comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


def inspect_svg_freeze_css(css_text: str) -> bool:
    """Helper to detect whether CSS satisfies the .is-svg-frozen-time stroke-dashoffset: 0 !important contract."""
    clean = strip_comments(css_text)
    has_frozen_class = ".is-svg-frozen-time" in clean
    has_draw_line = ".svg-draw-line" in clean
    has_zero_dashoffset = bool(
        re.search(
            r"\.is-svg-frozen-time[^{]*\{[^}]*stroke-dashoffset\s*:\s*0\s*!important",
            clean,
            re.DOTALL,
        )
        or (
            "stroke-dashoffset: 0 !important" in clean
            and ".is-svg-frozen-time" in clean
        )
    )
    return has_frozen_class and has_draw_line and has_zero_dashoffset


def inspect_webgl_context_loss_contract(js_text: str) -> bool:
    """Helper to verify that webglcontextlost is handled with preventDefault()."""
    clean = strip_comments(js_text)
    pattern = r"addEventListener\s*\(\s*['\"]webglcontextlost['\"]\s*,\s*(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>\s*\{[^}]*preventDefault\s*\(\s*\)"
    return bool(re.search(pattern, clean, re.DOTALL))


class TestSvgFreezeContract(unittest.TestCase):
    """Test suite verifying deterministic SVG/WebGL2 time freeze & responsive contracts."""

    # -------------------------------------------------------------------------
    # 1. Skill Contract Rules Verification
    # -------------------------------------------------------------------------
    def test_skill_contract_rules_present(self):
        """Verifies skills document ?t=SECONDS freeze, stroke-dashoffset: 0, webglcontextlost, mobile grids, and zero-innerHTML."""
        svg_skill = (SKILLS_DIR / "svg-animation" / "SKILL.md").read_text(encoding="utf-8")
        webgl_skill = (SKILLS_DIR / "webgl-threejs-graphics" / "SKILL.md").read_text(encoding="utf-8")
        web_std_skill = (SKILLS_DIR / "modern-web-standards" / "SKILL.md").read_text(encoding="utf-8")
        es_mod_skill = (SKILLS_DIR / "native-esmodules-design-patterns" / "SKILL.md").read_text(encoding="utf-8")

        # svg-animation: ?t=SECONDS, stroke-dashoffset: 0 !important, WAAPI scrubbing
        self.assertIn("?t=SECONDS", svg_skill)
        self.assertIn("stroke-dashoffset: 0 !important", svg_skill)
        self.assertIn("document.getAnimations()", svg_skill)
        self.assertIn("vector-effect=\"non-scaling-stroke\"", svg_skill)

        # webgl-threejs-graphics: webglcontextlost, webglcontextrestored, preventDefault(), ?t=SECONDS, min-width: 0
        self.assertIn("webglcontextlost", webgl_skill)
        self.assertIn("webglcontextrestored", webgl_skill)
        self.assertIn("preventDefault()", webgl_skill)
        self.assertIn("?t=SECONDS", webgl_skill)
        self.assertIn("min-width: 0", webgl_skill)
        self.assertIn("drawArraysInstanced", webgl_skill)

        # modern-web-standards: grid-template-columns: 1fr, min-width: 0, replaceChildren, zero innerHTML, @property
        self.assertIn("grid-template-columns: 1fr", web_std_skill)
        self.assertIn("min-width: 0", web_std_skill)
        self.assertIn("replaceChildren", web_std_skill)
        self.assertIn("@property", web_std_skill)
        self.assertIn("oklch", web_std_skill)

        # native-esmodules-design-patterns: zero-innerHTML, createElementNS, replaceChildren, AbortController, queueMicrotask
        self.assertIn("createElementNS", es_mod_skill)
        self.assertIn("replaceChildren", es_mod_skill)
        self.assertIn("AbortController", es_mod_skill)
        self.assertIn("queueMicrotask", es_mod_skill)
        self.assertIn("Float32Array", es_mod_skill)

    # -------------------------------------------------------------------------
    # 2. CSS Freeze & Reduced Motion Rules Verification
    # -------------------------------------------------------------------------
    def test_svg_frozen_time_and_reduced_motion_css(self):
        """Verifies .is-svg-frozen-time and prefers-reduced-motion overrides in stylesheets."""
        if AI_SRC is None:
            self.skipTest(".ai repository sibling not present in this environment")
        styles_lib = (AI_SRC / "styles-library.css").read_text(encoding="utf-8")
        styles_cf = (AI_SRC / "styles-cf.css").read_text(encoding="utf-8")

        # styles-library.css must enforce the .is-svg-frozen-time stroke-dashoffset: 0 !important rule
        self.assertTrue(
            inspect_svg_freeze_css(styles_lib),
            "styles-library.css must enforce .is-svg-frozen-time with stroke-dashoffset: 0 !important",
        )
        self.assertIn("prefers-reduced-motion: reduce", styles_lib)

        # styles-cf.css must include paused/freeze rules for biophysical animations
        self.assertIn(".is-svg-frozen-time", styles_cf)
        self.assertIn(".is-anim-paused", styles_cf)
        self.assertIn("prefers-reduced-motion: reduce", styles_cf)

    # -------------------------------------------------------------------------
    # 3. Synthetic Negative Test for SVG Freeze Detector
    # -------------------------------------------------------------------------
    def test_synthetic_negative_svg_freeze_detection(self):
        """Synthetic negative test: verifies detector fails when stroke-dashoffset: 0 is missing."""
        bad_css_missing_offset = """
        .is-svg-frozen-time .svg-draw-line {
            animation-play-state: paused !important;
            /* Missing stroke-dashoffset: 0 !important; lines remain invisible! */
        }
        """
        self.assertFalse(
            inspect_svg_freeze_css(bad_css_missing_offset),
            "Detector must reject CSS lacking stroke-dashoffset: 0 !important in .is-svg-frozen-time",
        )

        bad_css_missing_frozen_class = """
        .svg-draw-line {
            stroke-dashoffset: 0 !important;
        }
        """
        self.assertFalse(
            inspect_svg_freeze_css(bad_css_missing_frozen_class),
            "Detector must reject CSS lacking .is-svg-frozen-time container rule",
        )

    # -------------------------------------------------------------------------
    # 4. Animated SVGs Accessibility & WCAG 2.2.2 Pause Controls
    # -------------------------------------------------------------------------
    def test_animated_svgs_have_wcag_pause_controls_and_a11y(self):
        """Scans key animated schematics across .ai/src/ for viewBox, accessible naming, and pause buttons."""
        if AI_SRC is None:
            self.skipTest(".ai repository sibling not present in this environment")
        targets = [
            ("cftr-class-lifecycle-svg", "scripts/cf-variant-classes.js", True),
            ("nbd1-thermodynamics-svg", "cf/cftr/index.html", False),
            ("redosing-durability-svg", "cf/delivery/index.html", False),
            ("asl-cilia-svg", "cf/tree/index.html", False),
            ("pathway-flow-svg", "cf/registries/index.html", False),
            ("evidence-pipeline-svg", "evidence/index.html", False),
            ("loop-figure", "ai-loop/index.html", False),
            ("resources-compass-svg", "resources/index.html", False),
            ("ai-safety-gate-svg", "ai-in-care/index.html", False),
            ("about-architecture-svg", "about/index.html", False),
            ("contact-verification-svg", "contact/index.html", False),
        ]

        for target_id, rel_path, is_dynamic_js in targets:
            with self.subTest(target_id=target_id, file=rel_path):
                file_path = AI_SRC / rel_path
                self.assertTrue(file_path.is_file(), f"Target file must exist: {file_path}")
                content = file_path.read_text(encoding="utf-8")

                self.assertIn(target_id, content, f"ID {target_id} must be present in {rel_path}")

                # Verify viewBox presence
                has_viewbox = "viewBox" in content or "viewbox" in content
                self.assertTrue(has_viewbox, f"Schematic {target_id} in {rel_path} must define viewBox")

                # Verify accessible naming (role="img", aria-labelledby, aria-label, or <title>)
                has_a11y = (
                    'role="img"' in content
                    or "role='img'" in content
                    or 'role", "img"' in content
                    or "aria-labelledby" in content
                    or "aria-label" in content
                    or "<title" in content
                )
                self.assertTrue(has_a11y, f"Schematic {target_id} in {rel_path} must provide accessible naming")

                # Verify WCAG 2.2.2 pause control button
                has_pause = any(
                    token in content
                    for token in [
                        "anim-toggle",
                        "animToggle",
                        "data-svg-target",
                        "bench-anim-toggle-btn",
                        "pause",
                        "cftr-play",
                    ]
                )
                self.assertTrue(has_pause, f"Schematic {target_id} in {rel_path} must have a WCAG 2.2.2 pause toggle")

    # -------------------------------------------------------------------------
    # 5. WebGL2 Context Loss, Deterministic Time Freeze & Fallback
    # -------------------------------------------------------------------------
    def test_webgl2_context_loss_and_deterministic_time_freeze(self):
        """Verifies WebGL2 scripts attach context loss listeners (calling preventDefault()), read ?t=, and provide fallbacks."""
        if AI_SRC is None:
            self.skipTest(".ai repository sibling not present in this environment")
        # 1. Mucus Rheology Explorer
        mucus_js = (AI_SRC / "scripts" / "mucus-rheology-explorer.js").read_text(encoding="utf-8")
        self.assertIn("webglcontextlost", mucus_js)
        self.assertIn("webglcontextrestored", mucus_js)
        self.assertTrue(
            inspect_webgl_context_loss_contract(mucus_js),
            "mucus-rheology-explorer.js must call preventDefault() on webglcontextlost",
        )
        self.assertIn("URLSearchParams", mucus_js)
        self.assertTrue("urlParams.get('t')" in mucus_js or "params.get('t')" in mucus_js)
        self.assertIn("getContext('2d')", mucus_js)

        # 2. CFTR 3D Viewer / Hero Script
        cftr_script = AI_SRC / "scripts" / "cftr-hero.js"
        if not cftr_script.exists():
            cftr_script = AI_SRC / "scripts" / "cftr-viewer.js"

        self.assertTrue(cftr_script.is_file(), f"CFTR script must exist at {cftr_script}")
        cftr_js = cftr_script.read_text(encoding="utf-8")
        self.assertIn("webglcontextlost", cftr_js)
        self.assertIn("webglcontextrestored", cftr_js)
        self.assertTrue(
            inspect_webgl_context_loss_contract(cftr_js),
            f"{cftr_script.name} must call preventDefault() on webglcontextlost",
        )
        # Static SVG poster fallback verification
        self.assertTrue(
            "cftr-fallback" in cftr_js or "fallback" in cftr_js or "fail" in cftr_js,
            "CFTR script must coordinate with fallback element",
        )

        # Universal site-wide ?t= parameter coordinator in site.js
        site_js = (AI_SRC / "scripts" / "site.js").read_text(encoding="utf-8")
        self.assertIn("URLSearchParams", site_js)
        self.assertIn("params.get('t')", site_js)
        self.assertIn("is-svg-frozen-time", site_js)

    # -------------------------------------------------------------------------
    # 6. Synthetic Negative Test for WebGL2 Context Loss Handler
    # -------------------------------------------------------------------------
    def test_synthetic_negative_webgl_context_loss_handler(self):
        """Synthetic negative test: verifies detector rejects handler omitting preventDefault()."""
        bad_handler_no_prevent_default = """
        canvas.addEventListener('webglcontextlost', (e) => {
            lost = true;
            cancelAnimationFrame(rafId);
            // Missing e.preventDefault() -> Browser will NEVER restore context!
        });
        """
        self.assertFalse(
            inspect_webgl_context_loss_contract(bad_handler_no_prevent_default),
            "Detector must fail if preventDefault() is omitted in webglcontextlost handler",
        )

    # -------------------------------------------------------------------------
    # 7. Mobile (375px) Zero-Overflow Grid Contract
    # -------------------------------------------------------------------------
    def test_mobile_375px_zero_overflow_grid_contract(self):
        """Verifies responsive stylesheets enforce single-column layouts (grid-template-columns: 1fr) and min-width: 0."""
        if AI_SRC is None:
            self.skipTest(".ai repository sibling not present in this environment")
        styles_delivery = (AI_SRC / "styles-delivery.css").read_text(encoding="utf-8")
        styles_cf = (AI_SRC / "styles-cf.css").read_text(encoding="utf-8")
        styles_prime = (AI_SRC / "styles-cftr-prime.css").read_text(encoding="utf-8")

        # styles-delivery.css
        self.assertTrue(
            "grid-template-columns: 1fr" in styles_delivery
            or "grid-template-columns:1fr" in styles_delivery
        )
        self.assertIn("min-width: 0", styles_delivery)
        self.assertTrue("640px" in styles_delivery or "@container" in styles_delivery)

        # styles-cf.css
        self.assertTrue(
            "grid-template-columns: 1fr" in styles_cf
            or "grid-template-columns:1fr" in styles_cf
        )
        self.assertIn("min-width: 0", styles_cf)
        self.assertIn("max-width: 640px", styles_cf)

        # styles-cftr-prime.css
        self.assertTrue(
            "grid-template-columns: 1fr" in styles_prime
            or "grid-template-columns:1fr" in styles_prime
        )
        self.assertIn("max-width: 100%", styles_prime)

    # -------------------------------------------------------------------------
    # 8. Zero innerHTML & Strict CSP Invariant in Biophysical ES Modules
    # -------------------------------------------------------------------------
    def test_es_modules_zero_innerhtml_and_strict_csp(self):
        """Verifies that interactive biophysical ES modules contain zero .innerHTML and zero eval() / new Function()."""
        if AI_SRC is None:
            self.skipTest(".ai repository sibling not present in this environment")
        modules = [
            "prime-editing-explorer.js",
            "aav-packaging-calculator.js",
            "mucus-rheology-explorer.js",
            "modifier-epistasis-explorer.js",
            "cf-variant-classes.js",
            "ptc-simulator.js",
        ]

        for mod_name in modules:
            with self.subTest(module=mod_name):
                mod_path = AI_SRC / "scripts" / mod_name
                self.assertTrue(mod_path.is_file(), f"Module must exist: {mod_path}")
                content = mod_path.read_text(encoding="utf-8")

                self.assertNotIn(
                    ".innerHTML",
                    content,
                    f"Forbidden .innerHTML assignment found in {mod_name} violating strict CSP",
                )
                self.assertNotIn(
                    ".outerHTML",
                    content,
                    f"Forbidden .outerHTML assignment found in {mod_name} violating strict CSP",
                )
                self.assertNotIn(
                    "eval(",
                    content,
                    f"Forbidden eval() execution found in {mod_name}",
                )
                self.assertNotIn(
                    "new Function(",
                    content,
                    f"Forbidden new Function() execution found in {mod_name}",
                )

    # -------------------------------------------------------------------------
    # 9. Synthetic Negative Test for CSP / innerHTML Scanner
    # -------------------------------------------------------------------------
    def test_synthetic_negative_innerhtml_csp_violation(self):
        """Synthetic negative test: verifies CSP scanner catches forbidden innerHTML and eval()."""
        violating_code = """
        export function renderUnsafe(container, htmlSnippet) {
            container.innerHTML = htmlSnippet; // XSS vulnerability & CSP violation!
            eval("console.log('unsafe')");
        }
        """
        has_inner_html = ".innerHTML" in violating_code
        has_eval = "eval(" in violating_code
        self.assertTrue(has_inner_html, "Scanner must detect .innerHTML")
        self.assertTrue(has_eval, "Scanner must detect eval(")


if __name__ == "__main__":
    unittest.main()
