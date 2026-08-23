#!/usr/bin/env python3
"""Backfill infra_memory.embedding for rows that still have NULL vectors.

Idempotent: only rows with embedding IS NULL are processed. Safe to re-run.

Usage:
  python smb-copilot/scripts/backfill_embeddings.py --dry-run
  python smb-copilot/scripts/backfill_embeddings.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python smb-copilot/scripts/backfill_embeddings.py` from repo root.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from aegis_smb_copilot.db.connection import close_pool  # noqa: E402
from aegis_smb_copilot.onboarding.service import backfill_missing_embeddings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count pending rows only; do not call model-router or write",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    args = parser.parse_args()

    try:
        count = backfill_missing_embeddings(dry_run=args.dry_run, limit=args.limit)
    finally:
        close_pool()

    if args.dry_run:
        print(f"pending_rows={count}")
    else:
        print(f"embedded_rows={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
