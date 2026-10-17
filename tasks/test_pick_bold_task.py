#!/usr/bin/env python3
"""Tests for tasks/pick_bold_task.py (no network: open pull requests come from a fixture file)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import pick_bold_task as pbt


def task(tid, *, repo="cf-lab", area="tooling", priority="P2", complexity="low", low=1, high=2,
         composite=5.0, status="ready", depends_on=None, **extra):
    t = {
        "id": tid, "title": f"title {tid}", "repo": repo, "area": area, "priority": priority,
        "complexity": complexity, "effort_hours": {"low": low, "high": high}, "status": status,
        "depends_on": depends_on or [], "review_tier": "elevated", "recommended_route": "local",
        "acceptance": "a command that proves it", "notes": "", "roi": {"composite_score": composite, "rationale": ""},
    }
    t.update(extra)
    return t


class PickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.human = self.dir / "HUMAN-TASKS.md"
        self.human.write_text("# Human tasks\n", encoding="utf-8")
        self.prs = self.dir / "prs.json"
        self.prs.write_text("[]", encoding="utf-8")
        self.attempts = self.dir / "attempts.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_picker(self, tasks, lane="security", *extra):
        board = self.dir / "board.json"
        board.write_text(json.dumps({"schema_version": 1, "tasks": tasks}), encoding="utf-8")
        argv = ["--lane", lane, "--board", str(board), "--human-file", str(self.human),
                "--open-prs-file", str(self.prs), "--attempts-file", str(self.attempts), *extra]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pbt.main(argv)
        return code, out.getvalue()

    def bundle_ids(self, tasks, lane="security", *extra):
        code, out = self.run_picker(tasks, lane, "--json", *extra)
        self.assertEqual(code, 0, out)
        return [t["id"] for t in json.loads(out)["bundle"]]

    # ---- ranking -------------------------------------------------------------------------
    def test_bigger_beats_cheaper_even_with_lower_roi_per_hour(self):
        small = task("T-0001", priority="P1", complexity="low", low=0.5, high=1.5, composite=6.0)
        big = task("T-0002", repo="cf-skills", priority="P2", complexity="high", low=8, high=16, composite=5.0)
        # small has the far better impact per hour (6/1.0 vs 5/12), yet the bold pick is the big one
        self.assertEqual(self.bundle_ids([small, big])[0], "T-0002")

    def test_impact_still_matters_among_equal_scope(self):
        a = task("T-0001", complexity="medium", low=3, high=5, composite=4.0, repo="cf-lab", area="tooling")
        b = task("T-0002", complexity="medium", low=3, high=5, composite=8.0, repo="cf-skills", area="skills")
        self.assertEqual(self.bundle_ids([a, b])[0], "T-0002")

    def test_missing_composite_falls_back_to_computed_roi(self):
        t = task("T-0001")
        t["roi"] = {}
        self.assertEqual(self.bundle_ids([t]), ["T-0001"])

    # ---- eligibility -----------------------------------------------------------------------
    def test_only_ready_tasks(self):
        tasks = [task("T-0001", status="proposed"), task("T-0002", status="done"),
                 task("T-0003", status="in_progress"), task("T-0004", status="dropped")]
        code, out = self.run_picker(tasks, "security", "--check")
        self.assertEqual(code, 20, out)

    def test_human_executor_and_flag_excluded(self):
        tasks = [task("T-0001", executor="human"), task("T-0002", human_required=True)]
        code, _ = self.run_picker(tasks, "security", "--check")
        self.assertEqual(code, 20)

    def test_listed_in_human_tasks_excluded(self):
        self.human.write_text("- [ ] T-0001 sign up for the key\n", encoding="utf-8")
        code, _ = self.run_picker([task("T-0001")], "security", "--check")
        self.assertEqual(code, 20)

    def test_human_gate_wording_excluded(self):
        code, _ = self.run_picker([task("T-0001", notes="Needs a permission letter from the registry")], "security", "--check")
        self.assertEqual(code, 20)

    def test_unfinished_dependency_excluded_finished_one_allowed(self):
        blocked = task("T-0002", depends_on=["T-0001"], complexity="high", low=8, high=12, composite=9)
        code, _ = self.run_picker([task("T-0001", status="ready", composite=1), blocked], "security", "--json")
        self.assertEqual(self.bundle_ids([task("T-0001", status="ready", composite=1), blocked]), ["T-0001"])
        self.assertEqual(self.bundle_ids([task("T-0001", status="done"), blocked]), ["T-0002"])

    # ---- lanes -----------------------------------------------------------------------------
    def test_lane_assignment(self):
        self.assertEqual(pbt.lane_of(task("T-1", repo=".ai", area="reliability")), "security")  # infra, not showcase work
        self.assertEqual(pbt.lane_of(task("T-1", repo=".ai", area="content")), "showcase")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-lab", area="web")), "showcase")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-lab", area="content")), "showcase")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-research", area="tooling")), "research")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-lab", area="science")), "research")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-lab", area="security")), "security")
        self.assertEqual(pbt.lane_of(task("T-1", repo="cf-skills", area="skills")), "security")
        self.assertEqual(pbt.lane_of(task("T-1", repo="channel", area="distribution")), "security")

    def test_each_lane_only_sees_its_own_tasks(self):
        tasks = [task("T-0001", repo="cf-lab", area="security"), task("T-0002", repo="cf-research", area="research"),
                 task("T-0003", repo=".ai", area="content")]  # content in .ai is showcase work
        self.assertEqual(self.bundle_ids(tasks, "security"), ["T-0001"])
        self.assertEqual(self.bundle_ids(tasks, "research"), ["T-0002"])
        self.assertEqual(self.bundle_ids(tasks, "showcase"), ["T-0003"])

    def test_non_git_repo_is_not_eligible(self):
        # external platforms without a git repo (e.g. channel) must not be handed to git worktrees
        external = task("T-0002", repo="channel", area="content")
        valid = task("T-0003", repo=".ai", area="content")
        self.assertEqual(self.bundle_ids([external, valid], "showcase"), ["T-0003"])

    # ---- capacity ------------------------------------------------------------------------------
    def test_open_sentinel_pr_blocks_only_its_lane(self):
        self.prs.write_text(json.dumps([{"repo": "cf-lab", "headRefName": "work/sentinel-security-t-0009"},
                                         {"repo": "cf-lab", "headRefName": "feature/other"}]), encoding="utf-8")
        tasks = [task("T-0001", repo="cf-lab", area="security"), task("T-0002", repo="cf-research", area="research")]
        code, out = self.run_picker(tasks, "security", "--check")
        self.assertEqual(code, 21, out)
        self.assertIn("already has an open sentinel pull request", out)
        code, _ = self.run_picker(tasks, "research", "--check")
        self.assertEqual(code, 0)

    def test_non_sentinel_branches_do_not_block(self):
        self.prs.write_text(json.dumps([{"repo": "cf-lab", "headRefName": "site/showcase-x"}]), encoding="utf-8")
        code, _ = self.run_picker([task("T-0001")], "security", "--check")
        self.assertEqual(code, 0)

    def test_unreadable_pull_requests_build_nothing(self):
        self.prs.write_text("not json", encoding="utf-8")
        code, out = self.run_picker([task("T-0001")], "security", "--check")
        self.assertEqual(code, 22, out)
        self.prs = self.dir / "missing.json"
        code, _ = self.run_picker([task("T-0001")], "security", "--check")
        self.assertEqual(code, 22)

    # ---- attempts ----------------------------------------------------------------------------
    def test_claim_records_attempts_and_json_does_not(self):
        t = [task("T-0001")]
        self.run_picker(t, "security", "--json")
        self.assertFalse(self.attempts.exists())
        code, out = self.run_picker(t, "security", "--claim")
        self.assertEqual(code, 0)
        self.assertEqual(list(json.loads(self.attempts.read_text()).keys()), ["T-0001"])
        self.assertEqual(json.loads(out)["branch"], "work/sentinel-security-t-0001")

    def test_task_failing_twice_is_parked_then_released_after_the_window(self):
        t = [task("T-0001")]
        self.run_picker(t, "security", "--claim", "--now", "2026-10-15T00:00:00Z")
        self.run_picker(t, "security", "--claim", "--now", "2026-10-15T06:00:00Z")
        code, _ = self.run_picker(t, "security", "--check", "--now", "2026-10-15T08:00:00Z")
        self.assertEqual(code, 20)
        code, _ = self.run_picker(t, "security", "--check", "--now", "2026-10-18T00:00:00Z")
        self.assertEqual(code, 0)

    # ---- bundling ----------------------------------------------------------------------------
    def test_bundle_takes_related_tasks_within_budget(self):
        tasks = [task("T-0001", complexity="high", low=2, high=4, composite=9),
                 task("T-0002", low=1, high=3, composite=6),
                 task("T-0003", low=1, high=3, composite=5),
                 task("T-0004", low=1, high=3, composite=4)]
        self.assertEqual(self.bundle_ids(tasks), ["T-0001", "T-0002", "T-0003"])  # max 3 tasks

    def test_bundle_respects_hour_budget(self):
        tasks = [task("T-0001", complexity="high", low=6, high=8, composite=9),
                 task("T-0002", low=1, high=3, composite=6)]
        self.assertEqual(self.bundle_ids(tasks, "security", "--max-bundle-hours", "8"), ["T-0001"])

    def test_bundle_never_mixes_repos_or_areas(self):
        tasks = [task("T-0001", complexity="high", low=2, high=4, composite=9, repo="cf-lab", area="tooling"),
                 task("T-0002", repo="cf-skills", area="tooling", composite=8),
                 task("T-0003", repo="cf-lab", area="security", composite=8)]
        self.assertEqual(self.bundle_ids(tasks), ["T-0001"])


    # ---- size ceiling and person-needed wording (blind review findings) -----------------------
    def test_single_task_above_the_ceiling_is_never_handed_out_and_is_reported(self):
        huge = task("T-0001", complexity="high", low=16, high=20, composite=9)
        code, out = self.run_picker([huge], "security", "--check")
        self.assertEqual(code, 20)
        self.assertIn("too big for one run", out)
        self.assertIn("T-0001", out)
        ok = task("T-0002", complexity="high", low=8, high=16, composite=5, repo="cf-skills")  # mean 12.0, at the ceiling
        self.assertEqual(self.bundle_ids([huge, ok]), ["T-0002"])

    def test_ceiling_is_configurable_and_json_lists_what_was_skipped(self):
        huge = task("T-0001", complexity="high", low=16, high=20, composite=9)
        ok = task("T-0002", repo="cf-skills", complexity="medium", low=3, high=5)
        code, out = self.run_picker([huge, ok], "security", "--json")
        self.assertEqual(json.loads(out)["too_big_to_hand_out"], ["T-0001"])
        self.assertEqual(self.bundle_ids([huge], "security", "--max-task-hours", "20"), ["T-0001"])

    def test_bundle_budget_never_drops_below_the_top_task(self):
        top = task("T-0001", complexity="high", low=8, high=12, composite=9)  # mean 10 > 8
        other = task("T-0002", low=1, high=3, composite=5)
        self.assertEqual(self.bundle_ids([top, other]), ["T-0001"])

    def test_task_that_points_at_a_human_task_is_excluded(self):
        self.human.write_text("- [ ] T-0011 registry scientist reads the draft\n", encoding="utf-8")
        pointing = task("T-0134", acceptance="A registry scientist signs off (T-0011) before publication")
        code, _ = self.run_picker([pointing], "research", "--check")
        self.assertEqual(code, 20)

    def test_review_by_a_person_wording_is_excluded(self):
        for text in ("needs human review before it ships", "a registry scientist review of the ledger",
                     "clinician review of the wording"):
            code, _ = self.run_picker([task("T-0001", acceptance=text)], "security", "--check")
            self.assertEqual(code, 20, text)

    def test_decide_tasks_belong_to_the_maintainer(self):
        code, _ = self.run_picker([task("T-0001", title="Decide the tagline against lab-voice", repo=".ai", area="content")],
                                  "showcase", "--check")
        self.assertEqual(code, 20)
        code, _ = self.run_picker([task("T-0002", title="Build the evidence section", repo=".ai", area="content")],
                                  "showcase", "--check")
        self.assertEqual(code, 0)

    def test_listed_task_is_excluded_even_when_its_text_only_names_itself(self):
        self.human.write_text("- T-0001 is listed only because of a typo\n", encoding="utf-8")
        # listed means gated; this documents that a listed task is excluded, even when it names only itself
        code, _ = self.run_picker([task("T-0001", acceptance="T-0001 passes")], "security", "--check")
        self.assertEqual(code, 20)

    def test_branch_names_are_accepted_by_the_worktree_helper(self):
        import importlib.util
        helper = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "workspace-siblings" / "scripts" / "worktrees.py"
        spec = importlib.util.spec_from_file_location("worktrees_helper", helper)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for lane, repo, area in (("security", "cf-lab", "security"), ("research", "cf-research", "research"), ("showcase", ".ai", "content")):
            code, out = self.run_picker([task("T-0123", repo=repo, area=area)], lane, "--json")
            self.assertEqual(code, 0, out)
            branch = json.loads(out)["branch"]
            self.assertTrue(mod.BRANCH_STD_RX.fullmatch(branch), f"worktrees.py would refuse {branch}")
            # and the capacity check recognizes the same branch as this lane's open pull request
            self.prs.write_text(json.dumps([{"repo": repo, "headRefName": branch}]), encoding="utf-8")
            code, _ = self.run_picker([task("T-0123", repo=repo, area=area)], lane, "--check")
            self.assertEqual(code, 21, f"{branch} did not block lane {lane}")
            self.prs.write_text("[]", encoding="utf-8")

    # ---- output ------------------------------------------------------------------------------
    def test_check_prints_reason_when_nothing_is_eligible(self):
        code, out = self.run_picker([], "showcase", "--check")
        self.assertEqual(code, 20)
        self.assertIn("no eligible ready task in lane showcase", out)

    def test_json_carries_what_the_agent_needs(self):
        code, out = self.run_picker([task("T-0001", complexity="medium", low=2, high=4)], "security", "--json")
        d = json.loads(out)
        t = d["bundle"][0]
        self.assertEqual((d["lane"], d["repo"], d["branch"]), ("security", "cf-lab", "work/sentinel-security-t-0001"))
        for key in ("id", "title", "acceptance", "review_tier", "recommended_route", "effort_hours"):
            self.assertIn(key, t)

    def test_draft_sentinel_pr_skips_its_task_without_freezing_the_lane(self):
        self.prs.write_text(
            json.dumps([{"repo": "cf-skills", "headRefName": "work/sentinel-security-t-0083", "isDraft": True}]),
            encoding="utf-8",
        )
        tasks = [
            task("T-0083", repo="cf-skills", area="skills", complexity="high", low=4, high=6, composite=9),
            task("T-0055", repo="cf-skills", area="skills", complexity="medium", low=2, high=4, composite=8),
        ]
        # Draft PR awaiting human sign-off does not exit 21; it skips T-0083 and picks T-0055
        self.assertEqual(self.bundle_ids(tasks, "security"), ["T-0055"])

    def test_expanded_person_needed_wording_is_excluded(self):
        for text in (
            "the human reads SKILL.md and confirms the licence",
            "Verified on a real Mac in Terminal",
            "Try the five paste-ready boxes on Gemini, ChatGPT and Microsoft Copilot",
            "AWAITING_HUMAN: waiting on maintainer sign-off",
        ):
            code, _ = self.run_picker([task("T-0001", acceptance=text)], "security", "--check")
            self.assertEqual(code, 20, text)

    def test_bundle_chains_direct_dependent_within_hour_budget(self):
        first = task("T-0171", repo="cf-research", area="research", complexity="medium", low=3, high=5, composite=8)
        second = task(
            "T-0172", repo="cf-research", area="research", complexity="medium", low=3, high=5,
            composite=8, depends_on=["T-0171"],
        )
        self.assertEqual(self.bundle_ids([first, second], "research", "--max-bundle-hours", "10"), ["T-0171", "T-0172"])

    def test_draft_pr_skips_multi_task_and_compact_ids(self):
        self.prs.write_text(
            json.dumps([{
                "repo": "cf-skills",
                "headRefName": "work/sentinel-security-t0083-t-0055",
                "isDraft": True,
                "title": "feat: complete T-0083 and T-0055 (plus T-0069)",
            }]),
            encoding="utf-8",
        )
        tasks = [
            task("T-0083", composite=10),
            task("T-0055", composite=9),
            task("T-0069", composite=8),
            task("T-0115", composite=5),
        ]
        self.assertEqual(self.bundle_ids(tasks, "security"), ["T-0115"])


class RealBoardTests(unittest.TestCase):
    def test_every_lane_runs_on_the_real_board_without_error(self):
        with tempfile.TemporaryDirectory() as d:
            prs = Path(d) / "prs.json"
            prs.write_text("[]", encoding="utf-8")
            for lane in pbt.LANES:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = pbt.main(["--lane", lane, "--json", "--open-prs-file", str(prs),
                                     "--attempts-file", str(Path(d) / "a.json")])
                self.assertIn(code, (0, 20), f"{lane}: {out.getvalue()[:200]}")
                if code == 0:
                    bundle = json.loads(out.getvalue())["bundle"]
                    self.assertTrue(bundle)
                    self.assertTrue(all(t["id"].startswith("T-") for t in bundle))


if __name__ == "__main__":
    unittest.main(verbosity=2)
