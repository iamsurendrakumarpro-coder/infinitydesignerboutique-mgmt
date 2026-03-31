#!/usr/bin/env python3
"""Cleanup AWS resources created for the project."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def clear_aws_env_credentials() -> None:
    for key in [
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]:
        os.environ.pop(key, None)


def clear_aws_key_credentials() -> None:
    for key in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]:
        os.environ.pop(key, None)


def aws_client(service_name: str, region: str | None = None):
    region_name = region or os.getenv("AWS_REGION", "ap-south-1")
    profile = os.getenv("AWS_PROFILE")
    if profile:
        session = boto3.Session(profile_name=profile, region_name=region_name)
        return session.client(service_name, region_name=region_name)
    return boto3.client(service_name, region_name=region_name)


def verify_credentials(region: str) -> None:
    sts = aws_client("sts", region)
    identity = sts.get_caller_identity()
    print(f"✓ AWS credentials verified: {identity['Arn']}")


def empty_bucket(s3, bucket_name: str) -> None:
    paginator = s3.get_paginator("list_object_versions")
    objects_to_delete = []
    for page in paginator.paginate(Bucket=bucket_name):
        for version in page.get("Versions", []):
            objects_to_delete.append({"Key": version["Key"], "VersionId": version["VersionId"]})
        for marker in page.get("DeleteMarkers", []):
            objects_to_delete.append({"Key": marker["Key"], "VersionId": marker["VersionId"]})

    for index in range(0, len(objects_to_delete), 1000):
        batch = objects_to_delete[index:index + 1000]
        s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})


def delete_bucket(region: str, bucket_name: str) -> None:
    s3 = aws_client("s3", region)
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchBucket", "NotFound"}:
            print(f"✓ S3 bucket already absent: {bucket_name}")
            return
        raise

    empty_bucket(s3, bucket_name)
    s3.delete_bucket(Bucket=bucket_name)
    print(f"✓ Deleted S3 bucket: {bucket_name}")


def delete_db_instance(region: str, db_identifier: str, delete_final_snapshot: bool, final_snapshot_id: str | None) -> None:
    rds = aws_client("rds", region)
    try:
        if delete_final_snapshot:
            if not final_snapshot_id:
                final_snapshot_id = f"{db_identifier}-final-snapshot"
            rds.delete_db_instance(
                DBInstanceIdentifier=db_identifier,
                SkipFinalSnapshot=False,
                FinalDBSnapshotIdentifier=final_snapshot_id,
                DeleteAutomatedBackups=True,
            )
            print(f"✓ Started RDS deletion with final snapshot: {final_snapshot_id}")
        else:
            rds.delete_db_instance(
                DBInstanceIdentifier=db_identifier,
                SkipFinalSnapshot=True,
                DeleteAutomatedBackups=True,
            )
            print(f"✓ Started RDS deletion without final snapshot: {db_identifier}")
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code == "DBInstanceNotFound":
            print(f"✓ RDS instance already absent: {db_identifier}")
            return
        if error_code == "InvalidDBInstanceState":
            print(f"⚠ RDS instance is not deletable yet: {db_identifier}")
            return
        raise


def delete_security_group(region: str, project_name: str) -> None:
    ec2 = aws_client("ec2", region)
    sg_name = f"{project_name}-rds-sg"
    response = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [sg_name]}]
    )
    if not response["SecurityGroups"]:
        print(f"✓ Security group already absent: {sg_name}")
        return
    group_id = response["SecurityGroups"][0]["GroupId"]
    try:
        ec2.delete_security_group(GroupId=group_id)
        print(f"✓ Deleted security group: {group_id}")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "DependencyViolation":
            print(f"⚠ Security group still in use: {group_id}")
            return
        raise


def delete_app_policy(region: str, project_name: str) -> None:
    iam = aws_client("iam", region)
    policy_name = f"{project_name}-app-policy"
    response = iam.list_policies(Scope="Local")
    policy_arn = None
    for policy in response.get("Policies", []):
        if policy["PolicyName"] == policy_name:
            policy_arn = policy["Arn"]
            break
    if not policy_arn:
        print(f"✓ IAM policy already absent: {policy_name}")
        return
    iam.delete_policy(PolicyArn=policy_arn)
    print(f"✓ Deleted IAM policy: {policy_name}")


def delete_user_inline_policies(iam, username: str) -> None:
    response = iam.list_user_policies(UserName=username)
    for policy_name in response.get("PolicyNames", []):
        iam.delete_user_policy(UserName=username, PolicyName=policy_name)
        print(f"✓ Deleted inline policy {policy_name} from {username}")


def delete_user_access_keys(iam, username: str) -> None:
    response = iam.list_access_keys(UserName=username)
    for key in response.get("AccessKeyMetadata", []):
        iam.delete_access_key(UserName=username, AccessKeyId=key["AccessKeyId"])
        print(f"✓ Deleted access key {key['AccessKeyId']} from {username}")


def delete_iam_user(region: str, username: str) -> None:
    iam = aws_client("iam", region)
    try:
        iam.get_user(UserName=username)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "NoSuchEntity":
            print(f"✓ IAM user already absent: {username}")
            return
        raise

    delete_user_access_keys(iam, username)
    delete_user_inline_policies(iam, username)
    iam.delete_user(UserName=username)
    print(f"✓ Deleted IAM user: {username}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cleanup AWS resources for the project")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--aws-profile", default=None)
    parser.add_argument("--use-default-credentials", action="store_true")
    parser.add_argument("--delete-final-snapshot", action="store_true")
    parser.add_argument("--final-snapshot-id", default=None)
    parser.add_argument("--delete-app-policy", action="store_true")
    parser.add_argument("--delete-iam-users", action="store_true")
    parser.add_argument("--username", default="infinity-app-user")
    parser.add_argument("--provisioning-username", default="infinity-provisioner-user")
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.use_default_credentials:
        clear_aws_env_credentials()
    if args.aws_profile:
        clear_aws_key_credentials()
        os.environ["AWS_PROFILE"] = args.aws_profile

    try:
        verify_credentials(args.region)
    except ProfileNotFound as error:
        print(f"✗ AWS profile error: {error}")
        return 1
    except NoCredentialsError:
        print("✗ AWS credentials not found.")
        return 1

    if not args.force:
        print("Cleanup plan:")
        print(f"  - RDS: {args.project_name}-db")
        print(f"  - S3: {args.project_name}-files-{args.region}")
        print(f"  - Security Group: {args.project_name}-rds-sg")
        if args.delete_app_policy:
            print(f"  - IAM policy: {args.project_name}-app-policy")
        if args.delete_iam_users:
            print(f"  - IAM users: {args.username}, {args.provisioning_username}")
        confirmation = input("Proceed with cleanup? (y/N): ").strip().lower()
        if confirmation != "y":
            print("Aborted.")
            return 0

    db_identifier = f"{args.project_name}-db"
    bucket_name = f"{args.project_name}-files-{args.region}"

    try:
        delete_db_instance(args.region, db_identifier, args.delete_final_snapshot, args.final_snapshot_id)
        delete_bucket(args.region, bucket_name)
        delete_security_group(args.region, args.project_name)
        if args.delete_app_policy:
            delete_app_policy(args.region, args.project_name)
        if args.delete_iam_users:
            delete_iam_user(args.region, args.username)
            delete_iam_user(args.region, args.provisioning_username)
    except ClientError as error:
        print(f"✗ AWS Error: {error.response['Error']['Message']}")
        return 1
    except Exception as error:
        print(f"✗ Error: {error}")
        return 1

    print("✓ Cleanup commands completed. Some AWS deletions may continue asynchronously.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())