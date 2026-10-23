#!/usr/bin/env python3
"""Unit tests for Automated Multi-Repo Agent Async Task Zombie & Background Worker Leak Guard."""
from __future__ import annotations

import ast
import asyncio
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_async_task_leaks import (  # noqa: E402
    TrackedTaskRegistry,
    audit_async_task_retention,
    audit_thread_daemon_invariants,
    run_full_async_leak_linter,
    safe_create_task,
    REPO_ROOT,
)


class TestCheckAsyncTaskLeaks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repo_root_async_leak_linter_pass(self) -> None:
        report = run_full_async_leak_linter(REPO_ROOT)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertGreater(report["files_scanned"], 50)

    def test_tracked_task_registry_lifecycle(self) -> None:
        registry = TrackedTaskRegistry("test-reg")

        async def _sample_coro() -> str:
            await asyncio.sleep(0.01)
            return "ok"

        async def _run() -> None:
            task = safe_create_task(_sample_coro(), registry=registry, name="sample")
            self.assertIn(task, registry.active_tasks)
            res = await task
            self.assertEqual(res, "ok")
            # After completion and callback execution, task is discarded
            await asyncio.sleep(0.01)
            self.assertNotIn(task, registry.active_tasks)

        asyncio.run(_run())

    def test_tracked_task_registry_cancel_all(self) -> None:
        registry = TrackedTaskRegistry("cancel-reg")

        async def _hanging_coro() -> None:
            await asyncio.sleep(100.0)

        async def _run() -> None:
            task = safe_create_task(_hanging_coro(), registry=registry)
            self.assertEqual(len(registry.active_tasks), 1)
            cancelled = registry.cancel_all()
            self.assertEqual(cancelled, 1)
            await registry.shutdown(wait=True, timeout=1.0)
            self.assertEqual(len(registry.active_tasks), 0)

        asyncio.run(_run())

    def test_untracked_task_detected(self) -> None:
        code = "import asyncio\nasync def run():\n    asyncio.create_task(some_coro())\n"
        tree = ast.parse(code)
        findings = audit_async_task_retention(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "ASYNC001_UNTRACKED_TASK")
        self.assertEqual(findings[0].severity, "ERROR")

    def test_assigned_task_pass(self) -> None:
        code = "import asyncio\nasync def run():\n    task = asyncio.create_task(some_coro())\n    tasks.add(task)\n"
        tree = ast.parse(code)
        findings = audit_async_task_retention(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 0)

    def test_noqa_task_leak_suppression(self) -> None:
        code = "import asyncio\nasync def run():\n    asyncio.create_task(some_coro())  # noqa: task-leak\n"
        tree = ast.parse(code)
        findings = audit_async_task_retention(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 0)

    def test_non_daemon_thread_detected(self) -> None:
        code = "import threading\nt = threading.Thread(target=worker)\nt.start()\n"
        tree = ast.parse(code)
        findings = audit_thread_daemon_invariants(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "THREAD001_NON_DAEMON_WORKER")
        self.assertIn("created without daemon=True", findings[0].message)

    def test_daemon_thread_kwarg_pass(self) -> None:
        code = "import threading\nt = threading.Thread(target=worker, daemon=True)\nt.start()\n"
        tree = ast.parse(code)
        findings = audit_thread_daemon_invariants(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 0)

    def test_daemon_thread_attribute_assignment_pass(self) -> None:
        code = "import threading\nt = threading.Thread(target=worker)\nt.daemon = True\nt.start()\n"
        tree = ast.parse(code)
        findings = audit_thread_daemon_invariants(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 0)

    def test_inline_daemon_thread_start_pass(self) -> None:
        code = "import threading\nthreading.Thread(target=worker, daemon=True).start()\n"
        tree = ast.parse(code)
        findings = audit_thread_daemon_invariants(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 0)

    def test_inline_non_daemon_thread_start_detected(self) -> None:
        code = "import threading\nthreading.Thread(target=worker).start()\n"
        tree = ast.parse(code)
        findings = audit_thread_daemon_invariants(tree, "test.py", code.splitlines())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "THREAD001_NON_DAEMON_WORKER")


if __name__ == "__main__":
    unittest.main()
