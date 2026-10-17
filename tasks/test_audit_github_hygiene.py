#!/usr/bin/env python3
"""Unit tests for tasks/audit_github_hygiene.py."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

import audit_github_hygiene as agh  # noqa: E402


class TestAuditGithubHygiene(unittest.TestCase):
    def test_redact_sensitive(self):
        text = "Key: ghp_1234567890123456789012 and token Bearer abcdef1234567890. Email: test@example.com"
        redacted = agh.redact_sensitive(text)
        self.assertNotIn("ghp_1234567890123456789012", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertNotIn("Bearer abcdef1234567890", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertIn("[REDACTED_EMAIL]", redacted)

    def test_detect_merge_conflicts(self):
        mock_data = {
            "cf-lab": [
                {
                    "number": 101,
                    "title": "Clean PR",
                    "headRefName": "feat/clean",
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": ""
                },
                {
                    "number": 102,
                    "title": "Conflicting PR",
                    "headRefName": "feat/conflict",
                    "mergeable": "CONFLICTING",
                    "mergeStateStatus": "DIRTY",
                    "reviewDecision": ""
                },
                {
                    "number": 103,
                    "title": "Dirty PR",
                    "headRefName": "feat/dirty",
                    "mergeable": "UNKNOWN",
                    "mergeStateStatus": "DIRTY",
                    "reviewDecision": ""
                }
            ]
        }
        res = agh.audit_prs("senseiewok", ["cf-lab"], pr_data=mock_data, check_threads=False)
        self.assertEqual(len(res["prs"]), 3)
        self.assertEqual(len(res["conflicts"]), 2)
        conflict_numbers = [c["number"] for c in res["conflicts"]]
        self.assertIn(102, conflict_numbers)
        self.assertIn(103, conflict_numbers)

    def test_detect_review_blockers(self):
        mock_data = {
            "cf-lab": [
                {
                    "number": 201,
                    "title": "Changes Requested PR",
                    "headRefName": "feat/review",
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "CHANGES_REQUESTED",
                    "unresolved_threads": []
                },
                {
                    "number": 202,
                    "title": "Comment Thread PR",
                    "headRefName": "feat/threads",
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "",
                    "unresolved_threads": [
                        {"author": "reviewer1", "snippet": "Please fix this test", "url": "https://github.com/..."}
                    ]
                }
            ]
        }
        res = agh.audit_prs("senseiewok", ["cf-lab"], pr_data=mock_data, check_threads=False)
        self.assertEqual(len(res["review_blockers"]), 2)
        blocker_numbers = [b["number"] for b in res["review_blockers"]]
        self.assertIn(201, blocker_numbers)
        self.assertIn(202, blocker_numbers)

    def test_offline_graceful_handling(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No gh command found")
            prs, err = agh.fetch_open_prs_gh("senseiewok", "cf-lab")
            self.assertIsNone(prs)
            self.assertIn("not found on PATH", err)

            res = agh.audit_prs("senseiewok", ["cf-lab"], pr_data=None, check_threads=False)
            self.assertEqual(len(res["errors"]), 1)
            self.assertIn("not found on PATH", res["errors"][0]["error"])

    def test_audit_human_gated_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            human_tasks_file = tmp / "HUMAN-TASKS.md"
            board_file = tmp / "board.json"

            human_tasks_content = """# Human Tasks
## 1. Sign-ups, Licences and API Keys
- [ ] **NCBI API key**: Optional rate limit.
- [x] **OpenAlex API key**: Acquired.

## 2. External Permission Letters & Outbound Communications
- [ ] **Send CFTR2 permission letter (T-0106)**: Request citation terms.

## 6. Council-Approved Tasks (Automated & Moved to Ready / Done)
- [ ] **T-0098**: Automated CI test.
"""
            human_tasks_file.write_text(human_tasks_content, encoding="utf-8")

            board_content = {
                "tasks": [
                    {
                        "id": "T-0106",
                        "title": "Send permission letters and record replies",
                        "status": "ready",
                        "executor": "human",
                        "human_required": True,
                        "depends_on": []
                    },
                    {
                        "id": "T-0200",
                        "title": "Automated task waiting on human letter",
                        "status": "ready",
                        "executor": "model",
                        "human_required": False,
                        "depends_on": ["T-0106"]
                    }
                ]
            }
            board_file.write_text(json.dumps(board_content), encoding="utf-8")

            audit = agh.audit_human_gated_tasks(human_tasks_file, board_file)
            pending = audit["pending_human_actions"]
            completed = audit["completed_human_actions"]
            blocked = audit["blocked_agent_tasks"]

            self.assertEqual(len(pending), 2)  # NCBI and CFTR2 (T-0098 in Section 6 is ignored)
            self.assertEqual(len(completed), 1)  # OpenAlex
            self.assertEqual(len(blocked), 1)
            self.assertEqual(blocked[0]["task_id"], "T-0200")
            self.assertEqual(blocked[0]["blocked_by_human_task"], "T-0106")

    def test_audit_worktrees_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_script = Path(tmpdir) / "worktrees.py"
            fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            simulated_stdout = """
REMOVE cf-lab | .worktrees/cf-lab/wt-1 | branch-1 | pull request merged, clean, nothing unpushed
KEEP   cf-lab | .worktrees/cf-lab/wt-2 | branch-2 | a pull request is open
SUMMARY 2 worktree(s): 1 removable, 1 kept
"""
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=simulated_stdout, stderr="")
                res = agh.audit_worktrees(Path(tmpdir), fake_script, github=False)
                self.assertEqual(len(res["removable"]), 1)
                self.assertEqual(len(res["kept"]), 1)
                self.assertEqual(res["removable"][0]["branch"], "branch-1")
                self.assertEqual(res["kept"][0]["branch"], "branch-2")

    def test_update_handoff_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_file = Path(tmpdir) / "handoff.md"
            handoff_file.write_text("# Existing Session Handoff\n\nSome notes here.\n", encoding="utf-8")

            digest = {
                "timestamp": "2026-10-17T09:00:00Z",
                "conflicts": [
                    {
                        "repo": "senseiewok/cf-lab",
                        "number": 120,
                        "title": "Conflicting Feature",
                        "branch": "feat/conflict",
                        "url": "https://github.com/senseiewok/cf-lab/pull/120",
                        "mergeable": "CONFLICTING",
                        "merge_state": "DIRTY"
                    }
                ],
                "review_blockers": [],
                "human_deliverables": {
                    "pending_human_actions": [
                        {"section": "Letters", "name": "CFTR2 Letter", "task_ids": ["T-0106"], "detail": "Pending dispatch"}
                    ]
                },
                "worktrees": {
                    "removable": [{"repo": "cf-lab", "path": ".worktrees/1", "branch": "b1", "reason": "merged"}]
                }
            }

            updated = agh.update_handoff_document(digest, handoff_path=handoff_file)
            self.assertTrue(updated)

            content = handoff_file.read_text(encoding="utf-8")
            self.assertIn("## GitHub Hygiene Sentinel: Maintainer Action Required", content)
            self.assertIn("cf-lab#120", content)
            self.assertIn("CFTR2 Letter", content)
            self.assertIn("1 removable worktrees detected", content)
            self.assertIn("# Existing Session Handoff", content)

    def test_run_github_hygiene_audit_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "digest.json"
            mock_pr_file = Path(tmpdir) / "mock_prs.json"
            mock_pr_file.write_text(json.dumps({
                "cf-lab": [
                    {"number": 99, "title": "Test PR", "headRefName": "work/test", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "reviewDecision": ""}
                ]
            }), encoding="utf-8")

            digest = agh.run_github_hygiene_audit(
                owner="senseiewok",
                repos=["cf-lab"],
                output_path=out_file,
                pr_data_file=mock_pr_file,
                skip_worktrees=True,
                update_handoff=False
            )

            self.assertTrue(out_file.is_file())
            self.assertEqual(digest["status"], "clean")
            self.assertEqual(digest["open_prs_count"], 1)
            self.assertEqual(digest["summary"]["conflicts_count"], 0)

    def test_default_repos_includes_ai(self):
        self.assertIn(".ai", agh.DEFAULT_REPOS)
        self.assertIn("cf-lab", agh.DEFAULT_REPOS)
        self.assertIn("cf-skills", agh.DEFAULT_REPOS)
        self.assertIn("cf-research", agh.DEFAULT_REPOS)

    def test_detect_ci_failures(self):
        mock_data = {
            ".ai": [
                {
                    "number": 95,
                    "title": "Delivery hypothesis explorer",
                    "headRefName": "work/delivery",
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "reviewDecision": "",
                    "statusCheckRollup": [
                        {
                            "name": "Checks (generators and static tests)",
                            "workflowName": "Deploy",
                            "conclusion": "FAILURE",
                            "detailsUrl": "https://github.com/senseiewok/.ai/actions/runs/123"
                        },
                        {
                            "name": "CodeQL",
                            "workflowName": "CodeQL",
                            "conclusion": "SUCCESS",
                            "detailsUrl": "https://github.com/senseiewok/.ai/actions/runs/124"
                        }
                    ]
                }
            ]
        }
        res = agh.audit_prs("senseiewok", [".ai"], pr_data=mock_data, check_threads=False)
        self.assertEqual(len(res["prs"]), 1)
        self.assertEqual(len(res["ci_failures"]), 1)
        self.assertEqual(res["ci_failures"][0]["number"], 95)
        self.assertEqual(res["ci_failures"][0]["failed_checks"][0]["name"], "Checks (generators and static tests)")
        self.assertEqual(res["ci_failures"][0]["failed_checks"][0]["conclusion"], "FAILURE")

    def test_update_handoff_document_ci_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_file = Path(tmpdir) / "handoff.md"
            handoff_file.write_text("# Session Handoff\n", encoding="utf-8")

            digest = {
                "timestamp": "2026-10-17T09:00:00Z",
                "conflicts": [],
                "review_blockers": [],
                "ci_failures": [
                    {
                        "repo": "senseiewok/.ai",
                        "number": 95,
                        "title": "Delivery Explorer",
                        "branch": "work/delivery",
                        "url": "https://github.com/senseiewok/.ai/pull/95",
                        "failed_checks": [
                            {"name": "Checks (generators and static tests)", "conclusion": "FAILURE"}
                        ]
                    }
                ],
                "human_deliverables": {"pending_human_actions": []},
                "worktrees": {"removable": []}
            }

            updated = agh.update_handoff_document(digest, handoff_path=handoff_file)
            self.assertTrue(updated)
            content = handoff_file.read_text(encoding="utf-8")
            self.assertIn("Failing CI Checks Detected", content)
            self.assertIn(".ai#95", content)
            self.assertIn("Checks (generators and static tests)", content)


if __name__ == "__main__":
    unittest.main()
