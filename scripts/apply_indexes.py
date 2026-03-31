#!/usr/bin/env python3
"""Apply performance indexes for PostgreSQL tables used by the app."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from utils.db.indexes import ensure_postgres_indexes


def main() -> None:
    result = ensure_postgres_indexes()
    print(f"Indexes attempted: {len(result['created']) + len(result['skipped_missing_table']) + len(result['failed'])}")
    print(f"Created or already present: {len(result['created'])}")
    print(f"Skipped (table missing): {len(result['skipped_missing_table'])}")
    print(f"Failed: {len(result['failed'])}")

    if result["failed"]:
        print("Failed index names:")
        for name in result["failed"]:
            print(f"- {name}")


if __name__ == "__main__":
    main()
