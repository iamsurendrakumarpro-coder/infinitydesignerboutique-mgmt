#!/usr/bin/env python3
"""
AWS Resource Setup Script for Infinity Designer Boutique

This script creates all necessary AWS resources for deploying the application:
  - RDS PostgreSQL database
  - S3 bucket for file storage
  - Security groups and IAM policies
  - Parameter Store for sensitive configuration

Usage:
  python scripts/aws_setup.py --project-name my-boutique --region ap-south-1

Prerequisites:
  - AWS CLI configured with credentials
  - boto3 installed: pip install boto3
  - IAM permissions to create RDS, S3, EC2, IAM resources
"""

import argparse
import json
import sys
from datetime import datetime

import boto3

# AWS clients
rds = boto3.client("rds")
s3 = boto3.client("s3")
ec2 = boto3.client("ec2")
iam = boto3.client("iam")
ssm = boto3.client("ssm")


def get_current_vpc():
    """Get the default VPC for the region."""
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not vpcs["Vpcs"]:
        print("ERROR: No default VPC found. Please create a VPC first.")
        sys.exit(1)
    return vpcs["Vpcs"][0]["VpcId"]


def get_default_subnets(vpc_id):
    """Get subnet IDs in the default VPC."""
    subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    return [subnet["SubnetId"] for subnet in subnets["Subnets"]]


def create_security_group(vpc_id, project_name, region):
    """Create a security group for RDS and allow PostgreSQL traffic."""
    sg_name = f"{project_name}-rds-sg"
    sg_description = f"Security group for {project_name} RDS database"

    try:
        sg = ec2.create_security_group(
            GroupName=sg_name, Description=sg_description, VpcId=vpc_id
        )
        sg_id = sg["GroupId"]
        print(f"✓ Created security group: {sg_id}")

        # Allow PostgreSQL from anywhere (restrict in production)
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpProtocol="tcp",
            FromPort=5432,
            ToPort=5432,
            IpRange={"CidrIp": "0.0.0.0/0", "Description": "PostgreSQL access"},
        )
        print(f"✓ Authorized PostgreSQL ingress on port 5432")
        return sg_id
    except Exception as e:
        print(f"ERROR creating security group: {e}")
        sys.exit(1)


def create_rds_instance(project_name, region, sg_id, password):
    """Create RDS PostgreSQL database instance."""
    db_identifier = f"{project_name}-db"
    db_name = project_name.replace("-", "_")

    try:
        response = rds.create_db_instance(
            DBInstanceIdentifier=db_identifier,
            DBInstanceClass="db.t3.micro",  # Free tier eligible
            Engine="postgres",
            EngineVersion="15.3",
            MasterUsername="dbadmin",
            MasterUserPassword=password,
            AllocatedStorage=20,  # 20 GB
            StorageType="gp2",
            DBName=db_name,
            VpcSecurityGroupIds=[sg_id],
            PubliclyAccessible=True,  # Set False in production
            BackupRetentionPeriod=7,
            PreferredBackupWindow="03:00-04:00",
            PreferredMaintenanceWindow="sun:04:00-sun:05:00",
            EnableCloudwatchLogsExports=["postgresql"],
            EnableBabelfish=False,
            MultiAZ=False,  # Single-AZ for cost savings
            StorageEncrypted=True,
            Tags=[
                {"Key": "Project", "Value": project_name},
                {"Key": "CreatedBy", "Value": "aws_setup.py"},
                {"Key": "CreatedAt", "Value": datetime.now().isoformat()},
            ],
        )

        print(f"✓ RDS instance creation initiated: {db_identifier}")
        print(f"  This will take 5-10 minutes to complete.")
        print(f"  Database name: {db_name}")
        print(f"  Master user: dbadmin")
        print(f"  Engine: PostgreSQL 15.3")
        return db_identifier
    except Exception as e:
        if "DBInstanceAlreadyExists" in str(e):
            print(f"⚠ RDS instance '{db_identifier}' already exists. Skipping creation.")
            return db_identifier
        print(f"ERROR creating RDS instance: {e}")
        sys.exit(1)


def create_s3_bucket(project_name, region):
    """Create S3 bucket for file storage."""
    bucket_name = f"{project_name}-files-{region}"

    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"✓ S3 bucket created: {bucket_name}")

        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"}
        )
        print(f"✓ S3 versioning enabled")

        # Block public access
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        print(f"✓ S3 public access blocked")

        return bucket_name
    except Exception as e:
        if "BucketAlreadyExists" in str(e) or "BucketAlreadyOwnedByYou" in str(e):
            print(f"⚠ S3 bucket '{bucket_name}' already exists. Skipping creation.")
            return bucket_name
        print(f"ERROR creating S3 bucket: {e}")
        sys.exit(1)


def create_iam_policy(project_name):
    """Create IAM policy for application access to S3."""
    policy_name = f"{project_name}-app-policy"
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3BucketAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                "Resource": [
                    f"arn:aws:s3:::*{project_name}*",
                    f"arn:aws:s3:::*{project_name}*/*",
                ],
            },
            {
                "Sid": "ParameterStoreAccess",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                "Resource": f"arn:aws:ssm:*:*:parameter/{project_name}/*",
            },
        ],
    }

    try:
        response = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
            Description=f"Policy for {project_name} application S3 and SSM access",
        )
        print(f"✓ IAM policy created: {policy_name}")
        return response["Policy"]["Arn"]
    except Exception as e:
        if "EntityAlreadyExists" in str(e):
            print(f"⚠ IAM policy '{policy_name}' already exists. Retrieving ARN.")
            # Get existing policy ARN
            response = iam.list_policies(Scope="Local")
            for policy in response["Policies"]:
                if policy["PolicyName"] == policy_name:
                    return policy["Arn"]
        print(f"ERROR creating IAM policy: {e}")
        return None


def store_config_in_parameter_store(project_name, config):
    """Store sensitive configuration in AWS Parameter Store."""
    try:
        for key, value in config.items():
            param_name = f"/{project_name}/{key}"
            ssm.put_parameter(
                Name=param_name,
                Value=value,
                Type="SecureString",
                Overwrite=True,
                Description=f"Configuration for {project_name}",
                Tags=[
                    {"Key": "Project", "Value": project_name},
                    {"Key": "CreatedBy", "Value": "aws_setup.py"},
                ],
            )
        print(f"✓ Configuration stored in Parameter Store")
    except Exception as e:
        print(f"⚠ Could not store in Parameter Store: {e}")


def get_rds_endpoint(db_identifier):
    """Get the RDS endpoint after instance is created."""
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        if response["DBInstances"]:
            instance = response["DBInstances"][0]
            if "Endpoint" in instance and instance["Endpoint"]:
                return instance["Endpoint"]["Address"]
        return None
    except Exception as e:
        print(f"⚠ Could not retrieve RDS endpoint: {e}")
        return None


def generate_env_file(
    output_file, project_name, db_identifier, bucket_name, region, password
):
    """Generate .env file with AWS resource details."""
    rds_endpoint = get_rds_endpoint(db_identifier)
    if not rds_endpoint:
        print(
            f"⚠ RDS instance is still being created. Endpoint will be available shortly."
        )
        print(f"  Use: aws rds describe-db-instances --db-instance-identifier {db_identifier}")
        rds_endpoint = f"[your-rds-endpoint].rds.{region}.amazonaws.com"

    db_name = project_name.replace("-", "_")

    env_content = f"""# ─────────────────────────────────────────────────────────────────────────────
# .env – AWS Deployment Configuration
# Generated by aws_setup.py on {datetime.now().isoformat()}
# ─────────────────────────────────────────────────────────────────────────────

# ── Flask Core ────────────────────────────────────────────────────────────────
FLASK_ENV=production
FLASK_SECRET_KEY={__import__("secrets").token_hex(32)}
FLASK_DEBUG=False
PORT=5000

# ── Session ───────────────────────────────────────────────────────────────────
SESSION_LIFETIME_SECONDS=28800

# ── Firebase / Firestore (keep for Firestore fallback) ─────────────────────────
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com

# ── Migration Providers ───────────────────────────────────────────────────────
# Switch to postgres for production deployment
APP_DB_PROVIDER=postgres
APP_STORAGE_PROVIDER=s3

# ── PostgreSQL Configuration ───────────────────────────────────────────────────
POSTGRES_HOST={rds_endpoint}
POSTGRES_PORT=5432
POSTGRES_DB={db_name}
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD={password}

# ── AWS S3 Configuration ──────────────────────────────────────────────────────
AWS_REGION={region}
AWS_S3_BUCKET={bucket_name}

# Optional: AWS credentials (if not using IAM roles)
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key

# ── Application ───────────────────────────────────────────────────────────────
BOUTIQUE_NAME=Infinity Designer Boutique

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS_ORIGINS=https://yourdomain.com

# ── Root Admin Seeding ─────────────────────────────────────────────────────────
ROOT_ADMIN_FULL_NAME=Root Admin
ROOT_ADMIN_PHONE=9999999999
ROOT_ADMIN_PIN=0000
"""

    with open(output_file, "w") as f:
        f.write(env_content)

    print(f"✓ Generated .env file: {output_file}")
    print(f"\n⚠ IMPORTANT: Review and update the following in {output_file}:")
    print(f"  1. POSTGRES_PASSWORD (you provided): {password}")
    print(f"  2. AWS credentials (if not using IAM roles)")
    print(f"  3. CORS_ORIGINS (set to your frontend domain)")
    print(f"  4. ROOT_ADMIN_* settings (production credentials)")


def main():
    parser = argparse.ArgumentParser(
        description="Setup AWS resources for Infinity Designer Boutique"
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name (e.g., 'infinity-boutique')",
    )
    parser.add_argument(
        "--region", default="ap-south-1", help="AWS region (default: ap-south-1)"
    )
    parser.add_argument(
        "--db-password",
        default=None,
        help="RDS database password (generated if not provided)",
    )
    parser.add_argument(
        "--output-env", default=".env.aws", help="Output .env file path"
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("AWS Resource Setup for Infinity Designer Boutique")
    print("=" * 70 + "\n")

    # Generate password if not provided
    if not args.db_password:
        import secrets

        args.db_password = secrets.token_urlsafe(16)
        print(f"Generated RDS password: {args.db_password}")
        print(f"⚠ Save this password somewhere safe!\n")

    print(f"Project Name: {args.project_name}")
    print(f"Region: {args.region}")
    print(f"Output File: {args.output_env}\n")

    # Get VPC and subnets
    print("Retrieving VPC configuration...")
    vpc_id = get_current_vpc()
    subnets = get_default_subnets(vpc_id)
    print(f"✓ Using VPC: {vpc_id}")
    print(f"✓ Found {len(subnets)} subnets\n")

    # Create security group
    print("Creating security group...")
    sg_id = create_security_group(vpc_id, args.project_name, args.region)
    print()

    # Create RDS instance
    print("Creating RDS PostgreSQL instance...")
    db_identifier = create_rds_instance(
        args.project_name, args.region, sg_id, args.db_password
    )
    print()

    # Create S3 bucket
    print("Creating S3 bucket...")
    bucket_name = create_s3_bucket(args.project_name, args.region)
    print()

    # Create IAM policy
    print("Creating IAM policy...")
    policy_arn = create_iam_policy(args.project_name)
    if policy_arn:
        print(f"✓ Policy ARN: {policy_arn}\n")
    else:
        print()

    # Generate .env file
    print("Generating .env file...")
    generate_env_file(
        args.output_env,
        args.project_name,
        db_identifier,
        bucket_name,
        args.region,
        args.db_password,
    )
    print()

    # Summary
    print("=" * 70)
    print("AWS Setup Complete!")
    print("=" * 70)
    print("\nNext Steps:")
    print(f"1. Wait 5-10 minutes for RDS instance to fully initialize")
    print(f"2. Review and update {args.output_env}")
    print(f"3. Run migrations: python scripts/migrate_firestore_to_postgres.py")
    print(f"4. Deploy the application")
    print()
    print("Resource Summary:")
    print(f"  - RDS Instance:  {db_identifier}")
    print(f"  - Database:      {args.project_name.replace('-', '_')}")
    print(f"  - S3 Bucket:     {bucket_name}")
    print(f"  - Security Group: {sg_id}")
    print(f"  - Region:        {args.region}")
    print()
    print("RDS Status:")
    print(
        f"  aws rds describe-db-instances --db-instance-identifier {db_identifier}"
    )
    print()


if __name__ == "__main__":
    main()
