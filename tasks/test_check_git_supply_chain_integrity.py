#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Git Submodule & External Dependency Supply Chain Linter."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_git_supply_chain_integrity import (  # noqa: E402
    audit_external_script_and_cdn_guard,
    audit_git_submodule_pinning,
    audit_third_party_skill_quarantine,
    parse_third_party_skills,
    run_full_supply_chain_linter,
    REPO_ROOT,
)


class TestCheckGitSupplyChainIntegrity(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repo_root_supply_chain_linter_pass(self) -> None:
        report = run_full_supply_chain_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreaterEqual(report["metadata"]["third_party_skills_count"], 4)

    def test_parse_third_party_skills(self) -> None:
        doc = self.root / "THIRD_PARTY_SKILLS.md"
        doc.write_text(
            "| `alpha-skill` | src | `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef` |\n"
            "| `beta-skill` | src | `fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210` |\n",
            encoding="utf-8",
        )
        skills = parse_third_party_skills(doc)
        self.assertEqual(skills, {"alpha-skill", "beta-skill"})

    def test_third_party_skill_quarantine_pass(self) -> None:
        errors, warnings, meta = audit_third_party_skill_quarantine(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertIn("frontend-design", meta["skills_quarantined"])
        self.assertIn("skill-creator", meta["skills_quarantined"])

    def test_third_party_skill_missing_gitignore(self) -> None:
        doc = self.root / "THIRD_PARTY_SKILLS.md"
        doc.write_text(
            "| `leaky-skill` | src | `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef` |\n",
            encoding="utf-8",
        )
        gi = self.root / ".gitignore"
        gi.write_text("# empty gitignore\n", encoding="utf-8")

        errors, _, _ = audit_third_party_skill_quarantine(self.root)
        self.assertTrue(any("leaky-skill" in e for e in errors))

    def test_submodule_secure_https_pass(self) -> None:
        gm = self.root / ".gitmodules"
        gm.write_text(
            '[submodule "vendor/lib"]\n\tpath = vendor/lib\n\turl = https://github.com/example/lib.git\n',
            encoding="utf-8",
        )
        errors, warnings, meta = audit_git_submodule_pinning(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["submodules_audited"], 1)

    def test_submodule_insecure_http_fail(self) -> None:
        gm = self.root / ".gitmodules"
        gm.write_text(
            '[submodule "vendor/insecure"]\n\tpath = vendor/insecure\n\turl = http://example.com/insecure.git\n',
            encoding="utf-8",
        )
        errors, _, _ = audit_git_submodule_pinning(self.root)
        self.assertTrue(any("Insecure or unvetted remote URL" in e for e in errors))

    def test_submodule_floating_branch_warn(self) -> None:
        gm = self.root / ".gitmodules"
        gm.write_text(
            '[submodule "vendor/floating"]\n\tpath = vendor/floating\n\turl = https://github.com/example/floating.git\n\tbranch = main\n',
            encoding="utf-8",
        )
        errors, warnings, _ = audit_git_submodule_pinning(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("tracks floating branch" in w for w in warnings))

    def test_external_cdn_script_detection(self) -> None:
        html_file = self.root / "index.html"
        html_file.write_text(
            '<!DOCTYPE html><html><head><script src="https://cdn.jsdelivr.net/npm/vue@3"></script></head><body></body></html>',
            encoding="utf-8",
        )
        errors, _, meta = audit_external_script_and_cdn_guard(self.root)
        self.assertTrue(any("Prohibited external CDN script" in e for e in errors))
        self.assertEqual(meta["external_resources_detected"], 1)

    def test_external_dynamic_import_detection(self) -> None:
        js_file = self.root / "main.js"
        js_file.write_text(
            'const module = await import("https://unpkg.com/lodash-es");',
            encoding="utf-8",
        )
        errors, _, meta = audit_external_script_and_cdn_guard(self.root)
        self.assertTrue(any("Prohibited dynamic import from external URL" in e for e in errors))
        self.assertEqual(meta["external_resources_detected"], 1)

    def test_clean_local_web_assets_pass(self) -> None:
        html_file = self.root / "index.html"
        html_file.write_text(
            '<!DOCTYPE html><html><head><script type="module" src="./app.js"></script></head><body></body></html>',
            encoding="utf-8",
        )
        js_file = self.root / "app.js"
        js_file.write_text(
            'import { helper } from "./helper.js"; console.log(helper);',
            encoding="utf-8",
        )
        errors, warnings, meta = audit_external_script_and_cdn_guard(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(meta["external_resources_detected"], 0)


if __name__ == "__main__":
    unittest.main()
