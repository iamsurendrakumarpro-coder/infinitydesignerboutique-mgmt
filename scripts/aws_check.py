#!/usr/bin/env python3
"""
AWS Resource Status & Verification Script

Check the status of AWS resources created for the application deployment.
Useful for verifying RDS is ready and retrieving connection details.

Usage:
  python scripts/aws_check.py --project-name my-boutique --region ap-south-1
"""

import argparse
import sys

import boto3

rds = boto3.client("rds")
s3 = boto3.client("s3")
ec2 = boto3.client("ec2")


def check_rds_instance(db_identifier, region):
    """Check RDS instance status and retrieve connection details."""
    print(f"\n{'=' * 70}")
    print("RDS PostgreSQL Instance")
    print("=" * 70)

    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        if not response["DBInstances"]:
            print("ERROR: RDS instance not found")
            return False

        instance = response["DBInstances"][0]
        status = instance["DBInstanceStatus"]
        engine = instance["Engine"]
        engine_version = instance["EngineVersion"]
        storage = instance["AllocatedStorage"]

        print(f"Identifier:      {db_identifier}")
        print(f"Status:          {status}")
        print(f"Engine:          {engine} {engine_version}")
        print(f"Storage:         {storage} GB")
        print(f"Instance Class:  {instance['DBInstanceClass']}")
        print(f"Master Username: {instance['MasterUsername']}")

        if instance["Endpoint"]:
            endpoint = instance["Endpoint"]["Address"]
            port = instance["Endpoint"]["Port"]
            print(f"Endpoint:        {endpoint}:{port}")
            print(f"Database:        {instance['DBName']}")
            return True
        else:
            print(f"Endpoint:        [Still creating...]")
            return status == "available"
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def check_s3_bucket(bucket_name, region):
    """Check S3 bucket status and configuration."""
    print(f"\n{'=' * 70}")
    print("S3 Storage Bucket")
    print("=" * 70)

    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket Name:     {bucket_name}")
        print(f"Region:          {region}")

        # Get bucket versioning
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        version_status = versioning.get("Status", "Disabled")
        print(f"Versioning:      {version_status}")

        # Get public access block
        try:
            public_block = s3.get_public_access_block(Bucket=bucket_name)
            config = public_block["PublicAccessBlockConfiguration"]
            print(f"Public Access:   Blocked" if all(config.values()) else "Not fully blocked")
        except:
            print(f"Public Access:   Unknown")

        # Get bucket size and object count
        cloudwatch = boto3.client("cloudwatch")
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "StandardIAStorageSize"},
                ],
                StartTime=boto3.Session().get_credentials() and
                __import__("datetime").datetime.utcnow()
                - __import__("datetime").timedelta(days=1),
                EndTime=__import__("datetime").datetime.utcnow(),
                Period=86400,
            )
            print(f"Status:          ✓ Available")
        except:
            print(f"Status:          ✓ Available")

        return True
    except Exception as e:
        print(f"ERROR: Bucket not found or error: {e}")
        return False


def check_security_group(project_name):
    """Find and display security group details."""
    print(f"\n{'=' * 70}")
    print("Security Group")
    print("=" * 70)

    try:
        sg_name = f"{project_name}-rds-sg"
        response = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [sg_name]}]
        )

        if not response["SecurityGroups"]:
            print(f"Security Group:  Not found")
            return False

        sg = response["SecurityGroups"][0]
        print(f"Group ID:        {sg['GroupId']}")
        print(f"Group Name:      {sg['GroupName']}")
        print(f"VPC ID:          {sg['VpcId']}")

        # List ingress rules
        if sg["IpPermissions"]:
            print(f"Ingress Rules:")
            for rule in sg["IpPermissions"]:
                protocol = rule.get("IpProtocol", "-")
                from_port = rule.get("FromPort", "-")
                to_port = rule.get("ToPort", "-")
                print(f"  - Protocol: {protocol}, Port: {from_port}-{to_port}")
        else:
            print(f"Ingress Rules:   None")

        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def generate_connection_string(db_identifier, region):
    """Generate PostgreSQL connection string."""
    print(f"\n{'=' * 70}")
    print("Connection Details")
    print("=" * 70)

    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        instance = response["DBInstances"][0]

        if not instance["Endpoint"]:
            print("ERROR: Endpoint not yet available. Please wait for RDS instance to finish initializing.")
            return

        endpoint = instance["Endpoint"]["Address"]
        port = instance["Endpoint"]["Port"]
        db_name = instance["DBName"]
        user = instance["MasterUsername"]

        connection_string = f"postgresql://{user}:PASSWORD@{endpoint}:{port}/{db_name}"
        print(f"\nPostgreSQL Connection String:")
        print(f"  {connection_string}")
        print(f"\nEnvironment Variables:")
        print(f"  POSTGRES_HOST={endpoint}")
        print(f"  POSTGRES_PORT={port}")
        print(f"  POSTGRES_DB={db_name}")
        print(f"  POSTGRES_USER={user}")
        print(f"  POSTGRES_PASSWORD=<your-password>")
    except Exception as e:
        print(f"ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Check AWS resources for Infinity Designer Boutique"
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name (e.g., 'infinity-boutique')",
    )
    parser.add_argument(
        "--region", default="ap-south-1", help="AWS region (default: ap-south-1)"
    )

    args = parser.parse_args()

    db_identifier = f"{args.project_name}-db"
    bucket_name = f"{args.project_name}-files-{args.region}"

    print("\n" + "=" * 70)
    print("AWS Resource Status Check")
    print("=" * 70)
    print(f"\nProject:  {args.project_name}")
    print(f"Region:   {args.region}\n")

    # Check each resource
    rds_ok = check_rds_instance(db_identifier, args.region)
    s3_ok = check_s3_bucket(bucket_name, args.region)
    sg_ok = check_security_group(args.project_name)

    # Generate connection string if RDS is ready
    if rds_ok:
        generate_connection_string(db_identifier, args.region)

    # Summary
    print(f"\n{'=' * 70}")
    print("Status Summary")
    print("=" * 70)
    print(f"RDS:             {'✓' if rds_ok else '✗'}")
    print(f"S3:              {'✓' if s3_ok else '✗'}")
    print(f"Security Group:  {'✓' if sg_ok else '✗'}")

    if not all([rds_ok, s3_ok, sg_ok]):
        print("\n⚠ Some resources are not ready. Please wait and try again.")
        sys.exit(1)

    print("\n✓ All resources are ready for deployment!")


if __name__ == "__main__":
    main()
