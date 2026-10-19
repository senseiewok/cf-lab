#!/usr/bin/env python3
"""Unified test runner for triage board and picker tests."""
import unittest
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_triage_board import *  # noqa: F401, F403
from test_pick_bold_task import *  # noqa: F401, F403

if __name__ == "__main__":
    unittest.main()
