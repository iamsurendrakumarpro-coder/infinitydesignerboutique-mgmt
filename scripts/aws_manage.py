#!/usr/bin/env python3
"""Single entry point for AWS bootstrap, setup, and status checks."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from aws_workflows import run_iam_setup, run_resource_check, run_resource_setup


SCRIPTS_DIR = Path(__file__).resolve().parent


def add_common_aws_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        default="ap-south-1",
        help="AWS region (default: ap-south-1)",
    )
    parser.add_argument(
        "--aws-profile",
        default=None,
        help="AWS profile to use",
    )
    parser.add_argument(
        "--use-default-credentials",
        action="store_true",
        help="Ignore AWS_* values from .env and use the default shared credentials chain",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage AWS bootstrap, provisioning, and status for Infinity Designer Boutique"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    iam_parser = subparsers.add_parser("iam", help="Create or update IAM users and local profiles")
    iam_parser.add_argument("--username", default="infinity-app-user")
    iam_parser.add_argument("--provisioning-username", default="infinity-provisioner-user")
    iam_parser.add_argument("--policy-name", default="InfinityAppPolicy")
    iam_parser.add_argument("--provisioning-policy-name", default="InfinityProvisioningPolicy")
    iam_parser.add_argument("--skip-write-profiles", action="store_true")
    add_common_aws_args(iam_parser)

    setup_parser = subparsers.add_parser("setup", help="Provision AWS resources")
    setup_parser.add_argument("--project-name", required=True)
    setup_parser.add_argument("--db-password", default=None)
    setup_parser.add_argument("--output-env", default=".env.aws")
    add_common_aws_args(setup_parser)

    check_parser = subparsers.add_parser("check", help="Check AWS resource status")
    check_parser.add_argument("--project-name", required=True)
    add_common_aws_args(check_parser)

    full_parser = subparsers.add_parser(
        "full-setup",
        help="Run IAM bootstrap, then resource setup, then a status check",
    )
    full_parser.add_argument("--project-name", required=True)
    full_parser.add_argument("--username", default="infinity-app-user")
    full_parser.add_argument("--provisioning-username", default="infinity-provisioner-user")
    full_parser.add_argument("--policy-name", default="InfinityAppPolicy")
    full_parser.add_argument("--provisioning-policy-name", default="InfinityProvisioningPolicy")
    full_parser.add_argument("--db-password", default=None)
    full_parser.add_argument("--output-env", default=".env.aws")
    full_parser.add_argument("--skip-write-profiles", action="store_true")
    add_common_aws_args(full_parser)

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Delegate to aws_cleanup.py",
    )
    cleanup_parser.add_argument("--project-name", required=True)
    cleanup_parser.add_argument("--delete-final-snapshot", action="store_true")
    cleanup_parser.add_argument("--final-snapshot-id", default=None)
    cleanup_parser.add_argument("--delete-app-policy", action="store_true")
    cleanup_parser.add_argument("--delete-iam-users", action="store_true")
    cleanup_parser.add_argument("--username", default="infinity-app-user")
    cleanup_parser.add_argument("--provisioning-username", default="infinity-provisioner-user")
    cleanup_parser.add_argument("--force", action="store_true")
    add_common_aws_args(cleanup_parser)

    return parser


def handle_iam(args: argparse.Namespace) -> int:
    return run_iam_setup(args)


def handle_setup(args: argparse.Namespace) -> int:
    return run_resource_setup(args)


def handle_check(args: argparse.Namespace) -> int:
    return run_resource_check(args)


def handle_cleanup(args: argparse.Namespace) -> int:
    command = ["--project-name", args.project_name]
    command.extend(["--region", args.region])
    if getattr(args, "aws_profile", None):
        command.extend(["--aws-profile", args.aws_profile])
    if getattr(args, "use_default_credentials", False):
        command.append("--use-default-credentials")
    if args.delete_final_snapshot:
        command.append("--delete-final-snapshot")
    if args.final_snapshot_id:
        command.extend(["--final-snapshot-id", args.final_snapshot_id])
    if args.delete_app_policy:
        command.append("--delete-app-policy")
    if args.delete_iam_users:
        command.append("--delete-iam-users")
        command.extend(["--username", args.username])
        command.extend(["--provisioning-username", args.provisioning_username])
    if args.force:
        command.append("--force")
    script_path = SCRIPTS_DIR / "aws_cleanup.py"
    result = subprocess.run([__import__("sys").executable, str(script_path), *command], check=False)
    return result.returncode


def handle_full_setup(args: argparse.Namespace) -> int:
    iam_args = argparse.Namespace(**vars(args))
    setup_args = argparse.Namespace(**vars(args))
    check_args = argparse.Namespace(**vars(args))

    iam_code = handle_iam(iam_args)
    if iam_code != 0:
        return iam_code

    if not args.aws_profile and not args.use_default_credentials:
        setup_args.aws_profile = "infinity-provisioner"
        check_args.aws_profile = "infinity-provisioner"

    setup_code = handle_setup(setup_args)
    if setup_code != 0:
        return setup_code
    return handle_check(check_args)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "iam":
        return handle_iam(args)
    if args.command == "setup":
        return handle_setup(args)
    if args.command == "check":
        return handle_check(args)
    if args.command == "cleanup":
        return handle_cleanup(args)
    if args.command == "full-setup":
        return handle_full_setup(args)
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())