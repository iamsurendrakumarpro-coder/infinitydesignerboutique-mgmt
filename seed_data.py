#!/usr/bin/env python3
"""Backward-compatible seed entrypoint for PostgreSQL-based local data setup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    seed_script = project_root / "scripts" / "seed_postgres_e2e.py"

    if not seed_script.exists():
        print("Error: scripts/seed_postgres_e2e.py was not found.")
        return 1

    print("Legacy seeding has been removed. Running PostgreSQL E2E seed instead...")
    result = subprocess.run([sys.executable, str(seed_script)], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
