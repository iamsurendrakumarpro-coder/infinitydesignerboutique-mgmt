#!/usr/bin/env python3
"""
IAM Service Account Setup Script

Creates an IAM user with programmatic access (access keys) and appropriate
permissions for the Infinity Designer Boutique application.

Usage:
    python scripts/setup_iam_user.py --username infinity-app-user --region ap-south-1

This script will:
1. Create an IAM user
2. Generate access keys
3. Attach RDS and S3 permissions
4. Display credentials for AWS CLI configuration
"""

import boto3
import json
import sys
import argparse
from botocore.exceptions import ClientError


def create_iam_user(username):
    """Create an IAM user for the application."""
    iam = boto3.client('iam')
    
    try:
        user = iam.create_user(UserName=username)
        print(f"✓ IAM user created: {username}")
        return user['User']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"⚠ IAM user already exists: {username}")
            user = iam.get_user(UserName=username)
            return user['User']
        else:
            raise


def create_access_keys(username):
    """Generate access keys for the IAM user."""
    iam = boto3.client('iam')
    
    try:
        keys = iam.create_access_key(UserName=username)
        return keys['AccessKey']
    except ClientError as e:
        if e.response['Error']['Code'] == 'LimitExceeded':
            print(f"⚠ Maximum access keys reached for {username}")
            print("  To create new keys, delete existing ones or use existing keys.")
            # List existing keys
            response = iam.list_access_keys(UserName=username)
            if response['AccessKeyMetadata']:
                print("\n  Existing access keys:")
                for key in response['AccessKeyMetadata']:
                    print(f"    - {key['AccessKeyId']} (Status: {key['Status']})")
            return None
        else:
            raise


def create_app_policy():
    """Create a policy with RDS, S3, and basic permissions."""
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "RDSAccess",
                "Effect": "Allow",
                "Action": [
                    "rds-db:connect"
                ],
                "Resource": "arn:aws:rds:*:*:db/*"
            },
            {
                "Sid": "S3BucketAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    "arn:aws:s3:::*",
                    "arn:aws:s3:::*/*"
                ]
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            },
            {
                "Sid": "EC2SecurityGroupAccess",
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeInstances",
                    "ec2:DescribeNetworkInterfaces"
                ],
                "Resource": "*"
            }
        ]
    }
    return policy_document


def attach_policy_to_user(username, policy_name, policy_document):
    """Attach inline policy to IAM user."""
    iam = boto3.client('iam')
    
    try:
        iam.put_user_policy(
            UserName=username,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"✓ Policy attached to {username}: {policy_name}")
    except ClientError as e:
        print(f"✗ Failed to attach policy: {e}")
        raise


def display_credentials(access_key):
    """Display credentials and AWS CLI configuration instructions."""
    if not access_key:
        print("\n⚠ Could not display credentials (no access key generated)")
        return
    
    print("\n" + "="*70)
    print("✓ IAM USER SETUP COMPLETE")
    print("="*70)
    print("\n📋 CREDENTIALS (save these securely):\n")
    print(f"  Access Key ID:     {access_key['AccessKeyId']}")
    print(f"  Secret Access Key: {access_key['SecretAccessKey']}")
    print("\n  ⚠️  IMPORTANT: Save these securely! You won't see the secret key again.")
    print("\n" + "="*70)
    print("CONFIGURE AWS CLI")
    print("="*70)
    print("\nRun this command:")
    print("  aws configure --profile infinity-app")
    print("\nWhen prompted, enter:")
    print(f"  AWS Access Key ID: {access_key['AccessKeyId']}")
    print(f"  AWS Secret Access Key: {access_key['SecretAccessKey']}")
    print("  Default region: ap-south-1  (or your region)")
    print("  Default output format: json")
    print("\n" + "="*70)
    print("VERIFY SETUP")
    print("="*70)
    print("\nTest credentials:")
    print("  aws sts get-caller-identity --profile infinity-app")
    print("\nExpected output:")
    print("  {")
    print("    \"UserId\": \"...\",")
    print("    \"Account\": \"123456789012\",")
    print("    \"Arn\": \"arn:aws:iam::123456789012:user/infinity-app-user\"")
    print("  }")
    print("\n" + "="*70)
    print("USE IN FLASK APP")
    print("="*70)
    print("\nAdd to your .env file:")
    print(f"  AWS_ACCESS_KEY_ID={access_key['AccessKeyId']}")
    print(f"  AWS_SECRET_ACCESS_KEY={access_key['SecretAccessKey']}")
    print("  AWS_REGION=ap-south-1")
    print("\nOR use AWS_PROFILE:")
    print("  AWS_PROFILE=infinity-app")
    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Set up IAM service account for Infinity Designer Boutique'
    )
    parser.add_argument(
        '--username',
        default='infinity-app-user',
        help='IAM username (default: infinity-app-user)'
    )
    parser.add_argument(
        '--policy-name',
        default='InfinityAppPolicy',
        help='Policy name (default: InfinityAppPolicy)'
    )
    parser.add_argument(
        '--region',
        default='ap-south-1',
        help='AWS region (default: ap-south-1)'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("IAM SERVICE ACCOUNT SETUP")
    print("="*70)
    print(f"\nUsername: {args.username}")
    print(f"Region: {args.region}")
    print(f"Policy Name: {args.policy_name}")
    print("\n" + "-"*70)
    
    try:
        # Verify root credentials work
        sts = boto3.client('sts', region_name=args.region)
        identity = sts.get_caller_identity()
        print(f"✓ AWS credentials verified")
        print(f"  Account: {identity['Account']}")
        print(f"  ARN: {identity['Arn']}")
        
        if ':user/' in identity['Arn']:
            print("\n⚠ WARNING: You're using an IAM user account.")
            print("  Root user access is recommended for IAM setup.")
            response = input("\nContinue anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("Aborted.")
                return
        
        print("\n" + "-"*70)
        
        # Create IAM user
        create_iam_user(args.username)
        
        # Generate access keys
        access_key = create_access_keys(args.username)
        
        if not access_key:
            print("\n⚠ Failed to create access keys. Check existing keys and quotas.")
            return
        
        # Create and attach policy
        policy_doc = create_app_policy()
        attach_policy_to_user(args.username, args.policy_name, policy_doc)
        
        # Display setup instructions
        display_credentials(access_key)
        
        print("\n✓ Setup complete! Proceed with AWS CLI configuration.")
        
    except ClientError as e:
        print(f"\n✗ AWS Error: {e.response['Error']['Message']}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
