#!/usr/bin/env python3
"""Shared AWS workflow functions used by aws_manage.py."""

from __future__ import annotations

import configparser
import json
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

rds = None
s3 = None
ec2 = None
iam = None
ssm = None


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


def apply_auth_overrides(args) -> None:
    if getattr(args, "use_default_credentials", False):
        clear_aws_env_credentials()
    if getattr(args, "aws_profile", None):
        clear_aws_key_credentials()
        os.environ["AWS_PROFILE"] = args.aws_profile


def configure_clients(region: str):
    global rds, s3, ec2, iam, ssm
    rds = aws_client("rds", region)
    s3 = aws_client("s3", region)
    ec2 = aws_client("ec2", region)
    iam = aws_client("iam", region)
    ssm = aws_client("ssm", region)
    sts = aws_client("sts", region)
    identity = sts.get_caller_identity()
    return identity


def create_iam_user(username: str):
    try:
        user = iam.create_user(UserName=username)
        print(f"✓ IAM user created: {username}")
        return user["User"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"⚠ IAM user already exists: {username}")
            return iam.get_user(UserName=username)["User"]
        raise


def create_access_keys(username: str):
    try:
        keys = iam.create_access_key(UserName=username)
        return keys["AccessKey"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "LimitExceeded":
            print(f"⚠ Maximum access keys reached for {username}")
            print("  To create new keys, delete existing ones or use existing keys.")
            response = iam.list_access_keys(UserName=username)
            if response["AccessKeyMetadata"]:
                print("\n  Existing access keys:")
                for key in response["AccessKeyMetadata"]:
                    print(f"    - {key['AccessKeyId']} (Status: {key['Status']})")
            return None
        raise


def create_app_policy():
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "RDSAccess",
                "Effect": "Allow",
                "Action": ["rds-db:connect"],
                "Resource": "arn:aws:rds:*:*:db/*",
            },
            {
                "Sid": "S3BucketAccess",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
                "Resource": ["arn:aws:s3:::*", "arn:aws:s3:::*/*"],
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "arn:aws:logs:*:*:*",
            },
            {
                "Sid": "EC2SecurityGroupAccess",
                "Effect": "Allow",
                "Action": ["ec2:DescribeSecurityGroups", "ec2:DescribeInstances", "ec2:DescribeNetworkInterfaces"],
                "Resource": "*",
            },
        ],
    }


def create_provisioning_policy(project_name: str):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "RDSProvisioning",
                "Effect": "Allow",
                "Action": [
                    "rds:CreateDBInstance",
                    "rds:DeleteDBInstance",
                    "rds:DescribeDBInstances",
                    "rds:DescribeDBSnapshots",
                    "rds:ListTagsForResource",
                    "rds:AddTagsToResource",
                ],
                "Resource": "*",
            },
            {
                "Sid": "EC2NetworkProvisioning",
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:CreateSecurityGroup",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:DeleteSecurityGroup",
                ],
                "Resource": "*",
            },
            {
                "Sid": "S3Provisioning",
                "Effect": "Allow",
                "Action": [
                    "s3:CreateBucket",
                    "s3:DeleteBucket",
                    "s3:HeadBucket",
                    "s3:ListBucket",
                    "s3:ListBucketVersions",
                    "s3:GetBucketVersioning",
                    "s3:PutBucketVersioning",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                ],
                "Resource": "*",
            },
            {
                "Sid": "IAMPolicyProvisioning",
                "Effect": "Allow",
                "Action": ["iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:ListPolicies"],
                "Resource": "*",
            },
            {
                "Sid": "RDSServiceLinkedRole",
                "Effect": "Allow",
                "Action": ["iam:CreateServiceLinkedRole", "iam:GetRole"],
                "Resource": "*",
                "Condition": {"StringLike": {"iam:AWSServiceName": "rds.amazonaws.com"}},
            },
            {
                "Sid": "IAMUserBootstrap",
                "Effect": "Allow",
                "Action": [
                    "iam:CreateUser",
                    "iam:DeleteUser",
                    "iam:GetUser",
                    "iam:PutUserPolicy",
                    "iam:DeleteUserPolicy",
                    "iam:ListUserPolicies",
                    "iam:CreateAccessKey",
                    "iam:ListAccessKeys",
                    "iam:DeleteAccessKey",
                ],
                "Resource": "*",
            },
            {
                "Sid": "ReadIdentityAndMetrics",
                "Effect": "Allow",
                "Action": ["sts:GetCallerIdentity", "cloudwatch:GetMetricStatistics"],
                "Resource": "*",
            },
        ],
    }


def attach_policy_to_user(username: str, policy_name: str, policy_document):
    iam.put_user_policy(
        UserName=username,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(policy_document),
    )
    print(f"✓ Policy attached to {username}: {policy_name}")


def display_credentials(access_key, profile_name: str, region: str, section_title: str) -> None:
    if not access_key:
        print(f"\n⚠ Could not display credentials for {section_title} (no access key generated)")
        return
    print("\n" + "=" * 70)
    print(f"✓ {section_title} SETUP COMPLETE")
    print("=" * 70)
    print("\n📋 CREDENTIALS (save these securely):\n")
    print(f"  Access Key ID:     {access_key['AccessKeyId']}")
    print(f"  Secret Access Key: {access_key['SecretAccessKey']}")
    print("\n  IMPORTANT: Save these securely! You won't see the secret key again.")
    print("\nRun this command:")
    print(f"  aws configure --profile {profile_name}")
    print("\nWhen prompted, enter:")
    print(f"  AWS Access Key ID: {access_key['AccessKeyId']}")
    print(f"  AWS Secret Access Key: {access_key['SecretAccessKey']}")
    print(f"  Default region: {region}")
    print("  Default output format: json")


def configure_local_aws_profile(profile_name: str, access_key, region: str) -> None:
    if not access_key:
        return
    aws_dir = Path.home() / ".aws"
    aws_dir.mkdir(parents=True, exist_ok=True)
    credentials_path = aws_dir / "credentials"
    config_path = aws_dir / "config"
    credentials = configparser.RawConfigParser()
    config = configparser.RawConfigParser()
    if credentials_path.exists():
        credentials.read(credentials_path)
    if config_path.exists():
        config.read(config_path)
    if not credentials.has_section(profile_name):
        credentials.add_section(profile_name)
    credentials.set(profile_name, "aws_access_key_id", access_key["AccessKeyId"])
    credentials.set(profile_name, "aws_secret_access_key", access_key["SecretAccessKey"])
    config_section = "default" if profile_name == "default" else f"profile {profile_name}"
    if not config.has_section(config_section):
        config.add_section(config_section)
    config.set(config_section, "region", region)
    config.set(config_section, "output", "json")
    with open(credentials_path, "w", encoding="utf-8") as creds_file:
        credentials.write(creds_file)
    with open(config_path, "w", encoding="utf-8") as cfg_file:
        config.write(cfg_file)
    print(f"✓ Updated local AWS profile: {profile_name}")


def get_current_vpc():
    try:
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    except ClientError as error:
        print(f"ERROR retrieving VPC details: {error}")
        if "DescribeVpcs" in str(error) and "UnauthorizedOperation" in str(error):
            print("Hint: run with --aws-profile infinity-provisioner or --use-default-credentials")
        raise
    if not vpcs["Vpcs"]:
        raise RuntimeError("No default VPC found. Please create a VPC first.")
    return vpcs["Vpcs"][0]["VpcId"]


def get_default_subnets(vpc_id: str):
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    return [subnet["SubnetId"] for subnet in subnets["Subnets"]]


def create_security_group(vpc_id: str, project_name: str):
    sg_name = f"{project_name}-rds-sg"
    sg_description = f"Security group for {project_name} RDS database"

    def ensure_postgres_ingress(group_id: str):
        try:
            ec2.authorize_security_group_ingress(
                GroupId=group_id,
                IpProtocol="tcp",
                FromPort=5432,
                ToPort=5432,
                CidrIp="0.0.0.0/0",
            )
            print("✓ Authorized PostgreSQL ingress on port 5432")
        except Exception as ingress_error:
            if "InvalidPermission.Duplicate" in str(ingress_error):
                print("✓ PostgreSQL ingress already configured on port 5432")
            else:
                raise

    try:
        sg = ec2.create_security_group(GroupName=sg_name, Description=sg_description, VpcId=vpc_id)
        sg_id = sg["GroupId"]
        print(f"✓ Created security group: {sg_id}")
        ensure_postgres_ingress(sg_id)
        return sg_id
    except Exception as error:
        if "InvalidGroup.Duplicate" in str(error):
            existing = ec2.describe_security_groups(
                Filters=[
                    {"Name": "group-name", "Values": [sg_name]},
                    {"Name": "vpc-id", "Values": [vpc_id]},
                ]
            )
            if existing["SecurityGroups"]:
                sg_id = existing["SecurityGroups"][0]["GroupId"]
                print(f"⚠ Security group '{sg_name}' already exists: {sg_id}")
                ensure_postgres_ingress(sg_id)
                return sg_id
        raise


def create_rds_instance(project_name: str, sg_id: str, password: str):
    db_identifier = f"{project_name}-db"
    db_name = project_name.replace("-", "_")
    try:
        rds.create_db_instance(
            DBInstanceIdentifier=db_identifier,
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            MasterUsername="dbadmin",
            MasterUserPassword=password,
            AllocatedStorage=20,
            StorageType="gp2",
            DBName=db_name,
            VpcSecurityGroupIds=[sg_id],
            PubliclyAccessible=True,
            BackupRetentionPeriod=1,
            MultiAZ=False,
            StorageEncrypted=False,
            Tags=[
                {"Key": "Project", "Value": project_name},
                {"Key": "CreatedBy", "Value": "aws_manage.py"},
                {"Key": "CreatedAt", "Value": datetime.now().isoformat()},
            ],
        )
        print(f"✓ RDS instance creation initiated: {db_identifier}")
        print("  This will take 5-10 minutes to complete.")
        print(f"  Database name: {db_name}")
        print("  Master user: dbadmin")
        return db_identifier
    except Exception as error:
        if "DBInstanceAlreadyExists" in str(error):
            print(f"⚠ RDS instance '{db_identifier}' already exists. Skipping creation.")
            return db_identifier
        raise


def create_s3_bucket(project_name: str, region: str):
    bucket_name = f"{project_name}-files-{region}"
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
        print(f"✓ S3 bucket created: {bucket_name}")
        s3.put_bucket_versioning(Bucket=bucket_name, VersioningConfiguration={"Status": "Enabled"})
        print("✓ S3 versioning enabled")
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        print("✓ S3 public access blocked")
        return bucket_name
    except Exception as error:
        if "BucketAlreadyExists" in str(error) or "BucketAlreadyOwnedByYou" in str(error):
            print(f"⚠ S3 bucket '{bucket_name}' already exists. Skipping creation.")
            return bucket_name
        raise


def create_project_policy(project_name: str):
    policy_name = f"{project_name}-app-policy"
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3BucketAccess",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::*{project_name}*", f"arn:aws:s3:::*{project_name}*/*"],
            },
            {
                "Sid": "ParameterStoreAccess",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
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
    except Exception as error:
        if "EntityAlreadyExists" in str(error):
            print(f"⚠ IAM policy '{policy_name}' already exists. Retrieving ARN.")
            response = iam.list_policies(Scope="Local")
            for policy in response["Policies"]:
                if policy["PolicyName"] == policy_name:
                    return policy["Arn"]
        print(f"ERROR creating IAM policy: {error}")
        return None


def get_rds_endpoint(db_identifier: str):
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        if response["DBInstances"]:
            instance = response["DBInstances"][0]
            endpoint_info = instance.get("Endpoint")
            if endpoint_info:
                return endpoint_info["Address"]
        return None
    except Exception as error:
        print(f"⚠ Could not retrieve RDS endpoint: {error}")
        return None


def generate_env_file(output_file: str, project_name: str, db_identifier: str, bucket_name: str, region: str, password: str):
    rds_endpoint = get_rds_endpoint(db_identifier)
    if not rds_endpoint:
        print("⚠ RDS instance is still being created. Endpoint will be available shortly.")
        print(f"  Use: aws rds describe-db-instances --db-instance-identifier {db_identifier}")
        rds_endpoint = f"[your-rds-endpoint].rds.{region}.amazonaws.com"
    db_name = project_name.replace("-", "_")
    env_content = f"""# Generated by aws_manage.py on {datetime.now().isoformat()}\n\nFLASK_ENV=production\nFLASK_SECRET_KEY={secrets.token_hex(32)}\nFLASK_DEBUG=False\nPORT=5000\n\nSESSION_LIFETIME_SECONDS=28800\n\nPOSTGRES_HOST={rds_endpoint}\nPOSTGRES_PORT=5432\nPOSTGRES_DB={db_name}\nPOSTGRES_USER=dbadmin\nPOSTGRES_PASSWORD={password}\nPOSTGRES_SSLMODE=require\nPOSTGRES_CONNECT_TIMEOUT=10\n\nAWS_REGION={region}\nAWS_S3_BUCKET={bucket_name}\n\n# AWS_ACCESS_KEY_ID=your-access-key\n# AWS_SECRET_ACCESS_KEY=your-secret-key\n\nBOUTIQUE_NAME=Infinity Designer Boutique\nLOG_LEVEL=INFO\nCORS_ORIGINS=https://yourdomain.com\nROOT_ADMIN_FULL_NAME=Root Admin\nROOT_ADMIN_PHONE=9999999999\nROOT_ADMIN_PIN=0000\n"""
    with open(output_file, "w", encoding="utf-8") as file_handle:
        file_handle.write(env_content)
    print(f"✓ Generated .env file: {output_file}")
    print(f"\n⚠ IMPORTANT: Review and update the following in {output_file}:")
    print(f"  1. POSTGRES_PASSWORD (you provided): {password}")
    print("  2. AWS credentials (if not using IAM roles)")
    print("  3. CORS_ORIGINS (set to your frontend domain)")
    print("  4. ROOT_ADMIN_* settings (production credentials)")


def check_rds_instance(db_identifier: str):
    print(f"\n{'=' * 70}")
    print("RDS PostgreSQL Instance")
    print("=" * 70)
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        if not response["DBInstances"]:
            print("ERROR: RDS instance not found")
            return False
        instance = response["DBInstances"][0]
        print(f"Identifier:      {db_identifier}")
        print(f"Status:          {instance['DBInstanceStatus']}")
        print(f"Engine:          {instance['Engine']} {instance['EngineVersion']}")
        print(f"Storage:         {instance['AllocatedStorage']} GB")
        print(f"Instance Class:  {instance['DBInstanceClass']}")
        print(f"Master Username: {instance['MasterUsername']}")
        endpoint_info = instance.get("Endpoint")
        if endpoint_info:
            print(f"Endpoint:        {endpoint_info['Address']}:{endpoint_info['Port']}")
            print(f"Database:        {instance['DBName']}")
            return True
        print("Endpoint:        [Still creating...]")
        return instance["DBInstanceStatus"] == "available"
    except Exception as error:
        print(f"ERROR: {error}")
        return False


def check_s3_bucket(bucket_name: str, region: str):
    print(f"\n{'=' * 70}")
    print("S3 Storage Bucket")
    print("=" * 70)
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket Name:     {bucket_name}")
        print(f"Region:          {region}")
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        print(f"Versioning:      {versioning.get('Status', 'Disabled')}")
        try:
            public_block = s3.get_public_access_block(Bucket=bucket_name)
            config = public_block["PublicAccessBlockConfiguration"]
            print("Public Access:   Blocked" if all(config.values()) else "Public Access:   Not fully blocked")
        except Exception:
            print("Public Access:   Unknown")
        print("Status:          ✓ Available")
        return True
    except Exception as error:
        print(f"ERROR: Bucket not found or error: {error}")
        return False


def check_security_group(project_name: str):
    print(f"\n{'=' * 70}")
    print("Security Group")
    print("=" * 70)
    try:
        sg_name = f"{project_name}-rds-sg"
        response = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [sg_name]}])
        if not response["SecurityGroups"]:
            print("Security Group:  Not found")
            return False
        sg = response["SecurityGroups"][0]
        print(f"Group ID:        {sg['GroupId']}")
        print(f"Group Name:      {sg['GroupName']}")
        print(f"VPC ID:          {sg['VpcId']}")
        if sg["IpPermissions"]:
            print("Ingress Rules:")
            for rule in sg["IpPermissions"]:
                print(f"  - Protocol: {rule.get('IpProtocol', '-')}, Port: {rule.get('FromPort', '-')}-{rule.get('ToPort', '-')}")
        else:
            print("Ingress Rules:   None")
        return True
    except Exception as error:
        print(f"ERROR: {error}")
        return False


def generate_connection_string(db_identifier: str):
    print(f"\n{'=' * 70}")
    print("Connection Details")
    print("=" * 70)
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        instance = response["DBInstances"][0]
        endpoint_info = instance.get("Endpoint")
        if not endpoint_info:
            print("ERROR: Endpoint not yet available. Please wait for RDS instance to finish initializing.")
            return
        endpoint = endpoint_info["Address"]
        port = endpoint_info["Port"]
        db_name = instance["DBName"]
        user = instance["MasterUsername"]
        print("\nPostgreSQL Connection String:")
        print(f"  postgresql://{user}:PASSWORD@{endpoint}:{port}/{db_name}")
        print("\nEnvironment Variables:")
        print(f"  POSTGRES_HOST={endpoint}")
        print(f"  POSTGRES_PORT={port}")
        print(f"  POSTGRES_DB={db_name}")
        print(f"  POSTGRES_USER={user}")
        print("  POSTGRES_PASSWORD=<your-password>")
    except Exception as error:
        print(f"ERROR: {error}")


def run_iam_setup(args) -> int:
    apply_auth_overrides(args)
    print("=" * 70)
    print("IAM SERVICE ACCOUNT SETUP")
    print("=" * 70)
    print(f"\nUsername: {args.username}")
    print(f"Provisioning Username: {args.provisioning_username}")
    print(f"Region: {args.region}")
    print(f"Policy Name: {args.policy_name}")
    print(f"Provisioning Policy Name: {args.provisioning_policy_name}")
    print("\n" + "-" * 70)
    try:
        identity = configure_clients(args.region)
        print("✓ AWS credentials verified")
        print(f"  Account: {identity['Account']}")
        print(f"  ARN: {identity['Arn']}")
        if ":user/" in identity["Arn"]:
            print("\n⚠ WARNING: You're using an IAM user account.")
            print("  Root user access is recommended for IAM setup.")
            response = input("\nContinue anyway? (y/N): ").strip().lower()
            if response != "y":
                print("Aborted.")
                return 0
        print("\n" + "-" * 70)
        create_iam_user(args.username)
        attach_policy_to_user(args.username, args.policy_name, create_app_policy())
        app_access_key = create_access_keys(args.username)
        create_iam_user(args.provisioning_username)
        attach_policy_to_user(
            args.provisioning_username,
            args.provisioning_policy_name,
            create_provisioning_policy(args.username),
        )
        provisioning_access_key = create_access_keys(args.provisioning_username)
        display_credentials(app_access_key, "infinity-app", args.region, "APP RUNTIME IAM USER")
        display_credentials(provisioning_access_key, "infinity-provisioner", args.region, "PROVISIONING IAM USER")
        if not getattr(args, "skip_write_profiles", False):
            configure_local_aws_profile("infinity-app", app_access_key, args.region)
            configure_local_aws_profile("infinity-provisioner", provisioning_access_key, args.region)
        print("\nUse the provisioning profile for future infra commands:")
        print("  set AWS_PROFILE=infinity-provisioner")
        print("  python scripts/aws_manage.py setup --project-name infinity-boutique --region ap-south-1")
        print("\nUse the app profile for runtime app access:")
        print("  set AWS_PROFILE=infinity-app")
        print("  python app.py")
        print("\n✓ Setup complete! Proceed with AWS CLI configuration.")
        return 0
    except ProfileNotFound as error:
        print(f"\n✗ AWS profile error: {error}")
        print("Hint: verify AWS_PROFILE in .env or configure ~/.aws/credentials")
        return 1
    except NoCredentialsError:
        print("\n✗ AWS credentials not found.")
        print("Hint: set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in .env or configure ~/.aws/credentials")
        return 1
    except ClientError as error:
        print(f"\n✗ AWS Error: {error.response['Error']['Message']}")
        return 1
    except Exception as error:
        print(f"\n✗ Error: {error}")
        return 1


def run_resource_setup(args) -> int:
    apply_auth_overrides(args)
    print("\n" + "=" * 70)
    print("AWS Resource Setup for Infinity Designer Boutique")
    print("=" * 70 + "\n")
    if not args.db_password:
        args.db_password = secrets.token_urlsafe(16)
        print(f"Generated RDS password: {args.db_password}")
        print("⚠ Save this password somewhere safe!\n")
    print(f"Project Name: {args.project_name}")
    print(f"Region: {args.region}")
    print(f"Output File: {args.output_env}\n")
    if os.getenv("AWS_PROFILE"):
        print(f"AWS Profile: {os.getenv('AWS_PROFILE')}\n")
    try:
        identity = configure_clients(args.region)
        print(f"✓ AWS credentials verified: {identity['Arn']}\n")
        print("Retrieving VPC configuration...")
        vpc_id = get_current_vpc()
        subnets = get_default_subnets(vpc_id)
        print(f"✓ Using VPC: {vpc_id}")
        print(f"✓ Found {len(subnets)} subnets\n")
        print("Creating security group...")
        sg_id = create_security_group(vpc_id, args.project_name)
        print()
        print("Creating RDS PostgreSQL instance...")
        db_identifier = create_rds_instance(args.project_name, sg_id, args.db_password)
        print()
        print("Creating S3 bucket...")
        bucket_name = create_s3_bucket(args.project_name, args.region)
        print()
        print("Creating IAM policy...")
        policy_arn = create_project_policy(args.project_name)
        if policy_arn:
            print(f"✓ Policy ARN: {policy_arn}\n")
        else:
            print()
        print("Generating .env file...")
        generate_env_file(args.output_env, args.project_name, db_identifier, bucket_name, args.region, args.db_password)
        print()
        print("=" * 70)
        print("AWS Setup Complete!")
        print("=" * 70)
        print("\nNext Steps:")
        print("1. Wait 5-10 minutes for RDS instance to fully initialize")
        print(f"2. Review and update {args.output_env}")
        print("3. Initialize schema and seed test data if needed: python scripts/reset_seed_and_run.py --seed-only")
        print("4. Deploy the application")
        print("\nResource Summary:")
        print(f"  - RDS Instance:  {db_identifier}")
        print(f"  - Database:      {args.project_name.replace('-', '_')}")
        print(f"  - S3 Bucket:     {bucket_name}")
        print(f"  - Security Group: {sg_id}")
        print(f"  - Region:        {args.region}")
        print("\nRDS Status:")
        print(f"  aws rds describe-db-instances --db-instance-identifier {db_identifier}")
        return 0
    except ProfileNotFound as error:
        print(f"✗ AWS profile error: {error}")
        print("Hint: verify AWS_PROFILE in .env or configure ~/.aws/credentials")
        return 1
    except NoCredentialsError:
        print("✗ AWS credentials not found.")
        print("Hint: set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in .env or configure ~/.aws/credentials")
        return 1
    except Exception as error:
        print(f"✗ Error: {error}")
        return 1


def run_resource_check(args) -> int:
    apply_auth_overrides(args)
    try:
        identity = configure_clients(args.region)
        print(f"\n✓ AWS credentials verified: {identity['Arn']}")
    except ProfileNotFound as error:
        print(f"\n✗ AWS profile error: {error}")
        print("Hint: verify AWS_PROFILE in .env or configure ~/.aws/credentials")
        return 1
    except NoCredentialsError:
        print("\n✗ AWS credentials not found.")
        print("Hint: set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in .env or configure ~/.aws/credentials")
        return 1
    db_identifier = f"{args.project_name}-db"
    bucket_name = f"{args.project_name}-files-{args.region}"
    print("\n" + "=" * 70)
    print("AWS Resource Status Check")
    print("=" * 70)
    print(f"\nProject:  {args.project_name}")
    print(f"Region:   {args.region}\n")
    rds_ok = check_rds_instance(db_identifier)
    s3_ok = check_s3_bucket(bucket_name, args.region)
    sg_ok = check_security_group(args.project_name)
    if rds_ok:
        generate_connection_string(db_identifier)
    print(f"\n{'=' * 70}")
    print("Status Summary")
    print("=" * 70)
    print(f"RDS:             {'✓' if rds_ok else '✗'}")
    print(f"S3:              {'✓' if s3_ok else '✗'}")
    print(f"Security Group:  {'✓' if sg_ok else '✗'}")
    if not all([rds_ok, s3_ok, sg_ok]):
        print("\n⚠ Some resources are not ready. Please wait and try again.")
        return 1
    print("\n✓ All resources are ready for deployment!")
    return 0