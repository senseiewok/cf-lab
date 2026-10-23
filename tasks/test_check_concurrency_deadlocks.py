#!/usr/bin/env python3
"""Unit tests for tasks/check_concurrency_deadlocks.py."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tasks") not in sys.path:
    sys.path.insert(0, str(ROOT / "tasks"))

from check_concurrency_deadlocks import (
    audit_python_concurrency,
    bounded_lock,
    safe_thread_join,
    scan_workspace,
)


class TestCheckConcurrencyDeadlocks(unittest.TestCase):
    """Test AST deadlock analysis and safe concurrency primitives."""

    def test_bounded_lock_success(self):
        """Verify normal acquisition and release using bounded_lock."""
        lock = threading.Lock()
        with bounded_lock(lock, timeout=1.0) as acquired:
            self.assertTrue(acquired)
            self.assertTrue(lock.locked())
        self.assertFalse(lock.locked())

    def test_bounded_lock_timeout(self):
        """Verify TimeoutError raised when lock cannot be acquired within timeout."""
        lock = threading.Lock()
        lock.acquire()
        try:
            with self.assertRaises(TimeoutError):
                with bounded_lock(lock, timeout=0.05):
                    pass
        finally:
            lock.release()

    def test_safe_thread_join(self):
        """Verify safe_thread_join terminates gracefully on quick thread."""
        def quick_worker():
            time.sleep(0.01)

        t = threading.Thread(target=quick_worker, daemon=True)
        t.start()
        res = safe_thread_join(t, timeout=1.0)
        self.assertTrue(res)

    def test_detects_nested_asyncio_run(self):
        """Verify DEADLOCK-001 detection when asyncio.run() is called inside a coroutine."""
        code = """
import asyncio

async def bad_coroutine():
    asyncio.run(inner_coro())
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            rules = [item.rule for item in findings]
            self.assertIn("DEADLOCK-001", rules)
            err = next(item for item in findings if item.rule == "DEADLOCK-001")
            self.assertEqual(err.severity, "ERROR")
            self.assertIn("Nested event loop", err.message)
        finally:
            tmp_path.unlink()

    def test_detects_blocking_sleep_in_coroutine(self):
        """Verify DEADLOCK-001 detection when time.sleep() is called inside a coroutine."""
        code = """
import time

async def blocking_coroutine():
    time.sleep(5)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            rules = [item.rule for item in findings]
            self.assertIn("DEADLOCK-001", rules)
            err = next(item for item in findings if item.rule == "DEADLOCK-001")
            self.assertEqual(err.severity, "ERROR")
            self.assertIn("Synchronous blocking call", err.message)
        finally:
            tmp_path.unlink()

    def test_detects_unbounded_lock_acquire(self):
        """Verify DEADLOCK-002 detection when lock.acquire() lacks timeout."""
        code = """
def worker():
    my_lock.acquire()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            rules = [item.rule for item in findings]
            self.assertIn("DEADLOCK-002", rules)
            warn = next(item for item in findings if item.rule == "DEADLOCK-002")
            self.assertEqual(warn.severity, "WARNING")
        finally:
            tmp_path.unlink()

    def test_permits_bounded_lock_acquire(self):
        """Verify no findings when lock.acquire() includes a timeout."""
        code = """
def worker():
    my_lock.acquire(timeout=5.0)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            self.assertEqual(len(findings), 0)
        finally:
            tmp_path.unlink()

    def test_detects_unbounded_thread_join(self):
        """Verify DEADLOCK-003 detection on thread.join() without timeout."""
        code = """
def manager():
    worker_thread.join()
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            rules = [item.rule for item in findings]
            self.assertIn("DEADLOCK-003", rules)
        finally:
            tmp_path.unlink()

    def test_permits_bounded_thread_join(self):
        """Verify no findings when thread.join() includes timeout."""
        code = """
def manager():
    worker_thread.join(timeout=2.0)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            findings = audit_python_concurrency(tmp_path)
            self.assertEqual(len(findings), 0)
        finally:
            tmp_path.unlink()

    def test_scan_workspace_clean(self):
        """Verify workspace scan passes without errors."""
        findings, meta = scan_workspace(strict=False)
        self.assertTrue(meta["passed"])
        self.assertEqual(meta["errors"], 0)


if __name__ == "__main__":
    unittest.main()
