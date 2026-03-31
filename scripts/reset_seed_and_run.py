#!/usr/bin/env python3
"""One-command local bootstrap: reset DB, seed test data, and run app."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset PostgreSQL schema, seed E2E data, and start the Flask app"
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only reset+seed the database, do not start the app",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Keep schema and upsert seed data only",
    )
    parser.add_argument(
        "--python",
        dest="python_path",
        default=None,
        help="Explicit Python executable to use",
    )
    return parser.parse_args()


def resolve_python(project_root: Path, python_path: str | None) -> str:
    if python_path:
        return python_path

    sibling_venv_python = project_root.parent / "venv" / "Scripts" / "python.exe"
    if sibling_venv_python.exists():
        return str(sibling_venv_python)

    return sys.executable


def run_step(command: list[str], cwd: Path, env: dict[str, str], title: str) -> None:
    print(f"\n=== {title} ===")
    print(" ".join(command))
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    python_cmd = resolve_python(project_root, args.python_path)

    env = os.environ.copy()

    seed_script = project_root / "scripts" / "seed_postgres_e2e.py"
    seed_cmd = [python_cmd, str(seed_script)]
    if args.no_reset:
        seed_cmd.append("--no-reset")

    try:
        run_step(seed_cmd, project_root, env, "Reset + Seed PostgreSQL")
    except subprocess.CalledProcessError as exc:
        print(f"\nSeed step failed (exit code {exc.returncode}).")
        return exc.returncode

    print("\nSeed complete. Login credentials:")
    print("  Admin (root): 9999999999 / 0000")
    print("  Admin:        9876543210 / 1234")
    print("  Staff:        9123456789 / 5678")
    print("  URL:          http://127.0.0.1:5000")

    if args.seed_only:
        print("\nSeed-only mode enabled. App startup skipped.")
        return 0

    app_cmd = [python_cmd, str(project_root / "app.py")]
    try:
        run_step(app_cmd, project_root, env, "Start Flask App")
    except subprocess.CalledProcessError as exc:
        print(f"\nApp exited with code {exc.returncode}.")
        return exc.returncode
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
