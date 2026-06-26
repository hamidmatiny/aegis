#!/usr/bin/env python3
"""Deprecated wrapper — use run_same_corpus_comparison.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "run_same_corpus_comparison.py"
    raise SystemExit(subprocess.call([sys.executable, str(script), *sys.argv[1:]]))
