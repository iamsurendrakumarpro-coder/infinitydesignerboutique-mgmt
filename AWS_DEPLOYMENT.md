# AWS Deployment Guide
## Infinity Designer Boutique

This guide walks you through deploying the application to AWS with Postgres database and S3 storage.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Resource Architecture](#resource-architecture)
3. [Quick Start](#quick-start)
4. [Detailed Setup](#detailed-setup)
5. [Verification](#verification)
6. [Database Migration](#database-migration)
7. [Environment Configuration](#environment-configuration)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required

- **AWS Account** with appropriate permissions
- **AWS CLI** installed and configured with credentials
- **Python 3.10+** installed locally
- **boto3** package: `pip install boto3`
- **psycopg2** for database operations: `pip install psycopg2-binary`

### Permissions Required

Your AWS IAM user needs permissions for:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBInstance",
        "rds:DescribeDBInstances",
        "rds:DeleteDBInstance",
        "rds:ModifyDBInstance"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreatePolicy",
        "iam:ListPolicies",
        "iam:GetPolicy"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter"
      ],
      "Resource": "*"
    }
  ]
}
```

### Configure AWS CLI

```bash
aws configure
# Enter your Access Key ID, Secret Access Key, region (ap-south-1), output format (json)
```

---

## Resource Architecture

### AWS Resources Created

```
┌─────────────────────────────────────────┐
│      AWS Account (ap-south-1)           │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────────┐  │
│  │   RDS PostgreSQL Database         │  │
│  │  - Instance Class: db.t3.micro    │  │
│  │  - Engine: PostgreSQL 15.3        │  │
│  │  - Storage: 20GB (gp2)            │  │
│  │  - Backup: 7-day retention        │  │
│  └───────────────────────────────────┘  │
│           ↑        ↑                     │
│           │        │                     │
│  ┌────────┴────────┴────────────────┐   │
│  │   Security Group                │   │
│  │  - Allow PostgreSQL (port 5432)  │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │   S3 Bucket (File Storage)      │   │
│  │  - Versioning: Enabled          │   │
│  │  - Public Access: Blocked       │   │
│  │  - Encryption: Enabled          │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │   IAM Policy (App Permissions)  │   │
│  │  - S3 Bucket Access             │   │
│  │  - Parameter Store Access       │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

### Data Flow

```
Flask App
    ├─→ APP_DB_PROVIDER=postgres
    │        └─→ RDS PostgreSQL (5432)
    │
    └─→ APP_STORAGE_PROVIDER=s3
             └─→ S3 Bucket (file uploads: receipts, expenses, etc.)
```

---

## Quick Start

### Step 1: Install Dependencies

```bash
pip install boto3 psycopg2-binary
```

### Step 2: Run AWS Setup Script

```bash
cd infinitydesignerboutique-mgmt

python scripts/aws_setup.py \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --output-env .env.aws
```

**Output:**
```
======================================================================
AWS Resource Setup for Infinity Designer Boutique
======================================================================

Project Name: infinity-boutique
Region: ap-south-1
Output File: .env.aws

Retrieving VPC configuration...
✓ Using VPC: vpc-xxxxx
✓ Found 3 subnets

Creating security group...
✓ Created security group: sg-xxxxx
✓ Authorized PostgreSQL ingress on port 5432

Creating RDS PostgreSQL instance...
✓ RDS instance creation initiated: infinity-boutique-db
  This will take 5-10 minutes to complete.

Creating S3 bucket...
✓ S3 bucket created: infinity-boutique-files-ap-south-1
✓ S3 versioning enabled
✓ S3 public access blocked

Creating IAM policy...
✓ IAM policy created: infinity-boutique-app-policy

Generating .env file...
✓ Generated .env file: .env.aws
...

Next Steps:
1. Wait 5-10 minutes for RDS instance to fully initialize
2. Review and update .env.aws
3. Run migrations: python scripts/migrate_firestore_to_postgres.py
4. Deploy the application
```

### Step 3: Wait for RDS Instance

RDS takes 5-10 minutes to initialize. You can check progress with:

```bash
python scripts/aws_check.py \
  --project-name infinity-boutique \
  --region ap-south-1
```

### Step 4: Verify Resources

Once RDS is ready, review the generated `.env.aws` file and copy it to `.env`:

```bash
cp .env.aws .env
```

### Step 5: Run Database Migrations

```bash
# Create tables in your Postgres database
python scripts/migrate_firestore_to_postgres.py
```

### Step 6: Deploy Application

```bash
# Set provider to Postgres
export APP_DB_PROVIDER=postgres
export APP_STORAGE_PROVIDER=s3

# Start application
python app.py
```

---

## Detailed Setup

### A. Configure AWS CLI

1. **Create IAM User** (if you don't have one):
   - Go to AWS Console → IAM → Users → Create user
   - Attach policies listed in [Prerequisites](#prerequisites)
   - Create access key

2. **Configure AWS CLI**:
   ```bash
   aws configure
   # AWS Access Key ID: [paste your key]
   # AWS Secret Access Key: [paste your secret]
   # Default region name: ap-south-1
   # Default output format: json
   ```

3. **Verify Configuration**:
   ```bash
   aws sts get-caller-identity
   ```

### B. Customize Setup Script

Edit `scripts/aws_setup.py` to adjust:

```python
# Database configuration
"DBInstanceClass": "db.t3.micro",    # Free tier (change for prod)
"AllocatedStorage": 20,              # Size in GB
"BackupRetentionPeriod": 7,          # Days

# S3 configuration
"BlockPublicPolicy": True,           # Restrict public access
```

### C. Run Setup with Custom Password

```bash
python scripts/aws_setup.py \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --db-password your-secure-password-123 \
  --output-env .env.aws
```

**Password Requirements:**
- Minimum 8 characters
- Mix of uppercase, lowercase, numbers, and special characters
- NOT: admin, password, or sequential numbers

### D. Monitor RDS Creation

```bash
# Check status
aws rds describe-db-instances \
  --db-instance-identifier infinity-boutique-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address,AllocatedStorage]'

# Expected output (after 10 minutes):
# ["available", "infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com", 20]
```

---

## Verification

### Step 1: Check All Resources

```bash
python scripts/aws_check.py \
  --project-name infinity-boutique \
  --region ap-south-1
```

**Expected Output:**
```
======================================================================
RDS PostgreSQL Instance
======================================================================
Identifier:      infinity-boutique-db
Status:          available
Engine:          postgres 15.3
...

======================================================================
S3 Storage Bucket
======================================================================
Bucket Name:     infinity-boutique-files-ap-south-1
Region:          ap-south-1
Versioning:      Enabled
...

======================================================================
Connection Details
======================================================================
PostgreSQL Connection String:
  postgresql://dbadmin:PASSWORD@infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com:5432/infinity_boutique

Environment Variables:
  POSTGRES_HOST=infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com
  POSTGRES_PORT=5432
  POSTGRES_DB=infinity_boutique
  POSTGRES_USER=dbadmin
```

### Step 2: Test Database Connection

```bash
psql -h infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com \
     -U dbadmin \
     -d infinity_boutique \
     -c "SELECT version();"
```

### Step 3: Test S3 Access

```bash
# List buckets
aws s3 ls

# Upload test file
echo "test" > test.txt
aws s3 cp test.txt s3://infinity-boutique-files-ap-south-1/test.txt

# Download and verify
aws s3 cp s3://infinity-boutique-files-ap-south-1/test.txt test-downloaded.txt
cat test-downloaded.txt
```

### Step 4: Test Application

```bash
export APP_DB_PROVIDER=postgres
export POSTGRES_HOST=<your-rds-endpoint>
export POSTGRES_DB=infinity_boutique
export POSTGRES_USER=dbadmin
export POSTGRES_PASSWORD=<your-password>

python app.py
```

---

## Database Migration

### Migrate Firestore Data to Postgres

After RDS is ready and tables are created, migrate your existing Firestore data:

```bash
python scripts/migrate_firestore_to_postgres.py
```

This script:
1. Reads all data from Firestore collections
2. Transforms data to match Postgres schema
3. Inserts into corresponding Postgres tables
4. Logs migration progress and errors

### Create Initial Schema

The application automatically creates tables on first startup if they don't exist. You can also manually run:

```bash
python scripts/init_db.py
```

---

## Environment Configuration

### Generated `.env.aws` File

```bash
# ── Flask Core ────────────────────────────────────────────────────────────────
FLASK_ENV=production
FLASK_SECRET_KEY=<generated-hex-string>
FLASK_DEBUG=False

# ── Migration Providers ───────────────────────────────────────────────────────
APP_DB_PROVIDER=postgres              # Use Postgres instead of Firestore
APP_STORAGE_PROVIDER=s3               # Use S3 instead of Firestore

# ── PostgreSQL ────────────────────────────────────────────────────────────────
POSTGRES_HOST=infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=infinity_boutique
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=<your-password>

# ── AWS S3 ────────────────────────────────────────────────────────────────────
AWS_REGION=ap-south-1
AWS_S3_BUCKET=infinity-boutique-files-ap-south-1
```

### Additional Configuration (Optional)

```bash
# AWS credentials (if not using IAM roles)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# CORS for frontend
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Logging level
LOG_LEVEL=INFO

# Session timeout (seconds)
SESSION_LIFETIME_SECONDS=28800
```

---

## Troubleshooting

### RDS Instance Stuck in "Creating" Status

**Symptom:** `aws_check.py` shows status as "creating" after 15+ minutes

**Solution:**
```bash
# Check detailed logs
aws rds describe-db-instances \
  --db-instance-identifier infinity-boutique-db \
  --query 'DBInstances[0].[DBInstanceStatus,StatusInfos]'

# If stuck, reboot
aws rds reboot-db-instance \
  --db-instance-identifier infinity-boutique-db
```

### Cannot Connect to Database

**Symptom:** `psql: could not translate host name to address`

**Solutions:**
1. Verify endpoint is correct:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier infinity-boutique-db \
     --query 'DBInstances[0].Endpoint.Address'
   ```

2. Check security group allows your IP:
   ```bash
   aws ec2 describe-security-groups \
     --group-names infinity-boutique-rds-sg
   ```

3. Add your IP to security group:
   ```bash
   aws ec2 authorize-security-group-ingress \
     --group-name infinity-boutique-rds-sg \
     --protocol tcp \
     --port 5432 \
     --cidr <your-ip>/32
   ```

### S3 Upload Fails with Permission Error

**Symptom:** `An error occurred (AccessDenied) when calling the PutObject operation`

**Solution:**
1. Verify S3 bucket name in `.env`:
   ```bash
   echo $AWS_S3_BUCKET
   aws s3 ls s3://$AWS_S3_BUCKET
   ```

2. Check IAM permissions:
   ```bash
   aws iam list-policies --query 'Policies[?PolicyName==`infinity-boutique-app-policy`]'
   ```

3. If needed, attach policy to user:
   ```bash
   aws iam attach-user-policy \
     --user-name <your-username> \
     --policy-arn arn:aws:iam::123456789012:policy/infinity-boutique-app-policy
   ```

### Database Migration Fails

**Symptom:** Errors during `migrate_firestore_to_postgres.py`

**Solution:**
1. Verify Postgres is accessible:
   ```bash
   psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"
   ```

2. Check Firestore credentials:
   ```bash
   ls -la firebase-credentials.json
   ```

3. Run with verbose logging:
   ```bash
   python scripts/migrate_firestore_to_postgres.py --verbose
   ```

### Application Won't Start with Postgres

**Symptom:** `ModuleNotFoundError: No module named 'psycopg2'`

**Solution:**
```bash
pip install psycopg2-binary
```

**Other Issues:**
```bash
# Check environment variables
env | grep POSTGRES
env | grep AWS

# Verify database exists
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d postgres -l
```

---

## Next Steps

1. **Load Balancer**: Set up AWS Application Load Balancer (ALB)
2. **Monitoring**: Enable CloudWatch metrics and logs
3. **Backups**: Configure automated RDS backups and snapshots
4. **Certificate**: Use AWS Certificate Manager for HTTPS
5. **Auto-scaling**: Set up EC2 auto-scaling for the Flask app
6. **CDN**: Use CloudFront to cache S3 objects

---

## Production Checklist

- [ ] RDS: Change instance to `db.t3.small` or larger
- [ ] RDS: Enable multi-AZ for high availability
- [ ] RDS: Disable public access (`PubliclyAccessible=False`)
- [ ] S3: Enable encryption and logging
- [ ] Security Group: Restrict to app server IPs only
- [ ] Database: Change master password to a strong value
- [ ] Application: Set `FLASK_ENV=production`
- [ ] Application: Use strong `FLASK_SECRET_KEY`
- [ ] CORS: Set specific domain(s) instead of wildcard
- [ ] Logging: Set `LOG_LEVEL=WARNING` or `INFO`
- [ ] Backups: Verify RDS backups are running
- [ ] Monitoring: Set up CloudWatch alarms

---

## Support & Questions

For issues or questions:
1. Check logs: `docker logs <container-id>` or check app logs directory
2. Review AWS documentation: https://docs.aws.amazon.com/
3. Contact AWS Support (if you have a support plan)

---

**Last Updated:** 2026-03-29
