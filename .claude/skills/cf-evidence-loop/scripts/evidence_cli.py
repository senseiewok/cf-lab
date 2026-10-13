#!/usr/bin/env python3
"""Launcher so the skill runs from any working directory: python scripts/evidence_cli.py <command> ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
