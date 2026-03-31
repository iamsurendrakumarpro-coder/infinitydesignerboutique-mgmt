# AWS Deployment Scripts

Automated tools for deploying the Infinity Designer Boutique application to AWS.

## Quick Start

### Single Entry Point

```bash
# Full bootstrap + setup + check
python aws_manage.py full-setup --project-name infinity-boutique --region ap-south-1 --use-default-credentials

# Local app bootstrap (reset Postgres + seed lightweight data + run app)
python reset_seed_and_run.py

# Optional: choose a larger dataset profile when needed
python seed_postgres_e2e.py --size small

# Apply or re-check performance indexes
python apply_indexes.py

# Or run each phase separately
python aws_manage.py iam --use-default-credentials --region ap-south-1
python aws_manage.py setup --project-name infinity-boutique --aws-profile infinity-provisioner
python aws_manage.py check --project-name infinity-boutique --aws-profile infinity-provisioner

# Cleanup resources later
python aws_cleanup.py --project-name infinity-boutique --region ap-south-1 --aws-profile infinity-provisioner
```

### 1. Setup AWS Resources (5-15 minutes)

```bash
# Install dependencies
pip install boto3 psycopg2-binary

# Run setup
python aws_manage.py setup \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --aws-profile infinity-provisioner
```

This creates:
- ✅ RDS PostgreSQL database (db.t3.micro)
- ✅ S3 bucket for file storage
- ✅ Security groups & IAM policies
- ✅ `.env.aws` configuration file

### 2. Verify Resources (after RDS initializes)

```bash
python aws_manage.py check \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --aws-profile infinity-provisioner
```

Displays:
- ✅ RDS instance status & connection details
- ✅ S3 bucket configuration
- ✅ Security group rules
- ✅ PostgreSQL connection string

### 3. Initialize DB & Deploy

```bash
# Copy generated .env
cp .env.aws .env

# Initialize schema / seed local test data (optional)
python reset_seed_and_run.py --seed-only

# Ensure performance indexes exist
python apply_indexes.py

# Start application
python app.py
```

---

## Scripts

### `aws_manage.py`

**Purpose:** Single script for IAM bootstrap, setup, status checks, and cleanup delegation

**Commands:**
- `python aws_manage.py iam --use-default-credentials --region ap-south-1`
- `python aws_manage.py setup --project-name infinity-boutique --aws-profile infinity-provisioner`
- `python aws_manage.py check --project-name infinity-boutique --aws-profile infinity-provisioner`
- `python aws_manage.py full-setup --project-name infinity-boutique --use-default-credentials`
- `python aws_manage.py cleanup --project-name infinity-boutique --aws-profile infinity-provisioner`

### `aws_cleanup.py`

**Purpose:** Remove provisioned AWS resources for a project

**Usage:**
```bash
python aws_cleanup.py \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --aws-profile infinity-provisioner
```

**Optional flags:**
- `--delete-final-snapshot`: keep a final RDS snapshot instead of skipping it
- `--final-snapshot-id`: explicit final snapshot id to use with the flag above
- `--delete-app-policy`: remove the project IAM policy created during setup
- `--delete-iam-users`: also remove the IAM users created during bootstrap
- `--force`: skip confirmation prompt

### `aws_workflows.py`

**Purpose:** Internal shared workflow module used by `aws_manage.py`

This module contains the shared logic for:
- IAM bootstrap
- AWS resource provisioning
- Status checks
- `.env.aws` generation

**Example Output:**
```
======================================================================
AWS Resource Setup for Infinity Designer Boutique
======================================================================

✓ Using VPC: vpc-12345678
✓ Created security group: sg-87654321
✓ RDS instance creation initiated: infinity-boutique-db
✓ S3 bucket created: infinity-boutique-files-ap-south-1
✓ IAM policy created: infinity-boutique-app-policy
✓ Generated .env file: .env.aws

Next Steps:
1. Wait 5-10 minutes for RDS instance to fully initialize
2. Review and update .env.aws
3. Run: python aws_manage.py check --project-name infinity-boutique --aws-profile infinity-provisioner
```

---

## Setup Process

### Prerequisites

1. **AWS Account** with active credit card
2. **AWS CLI** installed: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
3. **AWS Credentials** configured:
   ```bash
   aws configure
   # Enter: Access Key, Secret Key, Region (ap-south-1), Format (json)
   ```
4. **IAM Permissions** (see [AWS_DEPLOYMENT.md](../AWS_DEPLOYMENT.md#prerequisites))

### Step-by-Step

#### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 2: Configure AWS CLI

```bash
aws configure

# Verify configuration
aws sts get-caller-identity
```

#### Step 3: Run Setup Script

```bash
python aws_manage.py setup --project-name infinity-boutique --region ap-south-1 --aws-profile infinity-provisioner
```

**⏱️ Wait 5-10 minutes for RDS to initialize**

#### Step 4: Verify Resources Are Ready

```bash
python aws_manage.py check --project-name infinity-boutique --region ap-south-1 --aws-profile infinity-provisioner
```

Wait for status to show `available` for RDS.

#### Step 5: Copy .env Configuration

```bash
cp .env.aws .env
```

**Edit `.env` to update:**
- Any placeholder values
- `CORS_ORIGINS` for your frontend domain
- `ROOT_ADMIN_*` for initial admin user

#### Step 6: Test Database Connection

```bash
# Using environment variables from .env
psql -h $POSTGRES_HOST \
     -U $POSTGRES_USER \
     -d $POSTGRES_DB \
     -c "SELECT version();"
```

#### Step 7: Deploy Application

```bash
# Start application
python app.py
```

---

## Troubleshooting

### Issue: "The AWS Access Key ID is invalid"

**Solution:**
```bash
# Reconfigure AWS CLI
aws configure

# Verify credentials
aws sts get-caller-identity
```

### Issue: RDS still "creating" after 15 minutes

**Solution:**
```bash
# Check detailed status
aws rds describe-db-instances \
  --db-instance-identifier infinity-boutique-db

# Reboot if stuck
aws rds reboot-db-instance \
  --db-instance-identifier infinity-boutique-db
```

### Issue: Cannot connect to database

**Solution:**
```bash
# Get endpoint
aws rds describe-db-instances \
  --db-instance-identifier infinity-boutique-db \
  --query 'DBInstances[0].Endpoint.Address'

# Test connection
psql -h <endpoint> -U dbadmin -d infinity_boutique
```

### Issue: S3 upload fails

**Solution:**
```bash
# Verify bucket exists
aws s3 ls s3://infinity-boutique-files-ap-south-1

# Check permissions
aws iam list-policies --query 'Policies[?contains(PolicyName, `infinity-boutique`)]'
```

---

## AWS Console Shortcuts

Monitor your resources in AWS Console:

```bash
# Open RDS console
open "https://console.aws.amazon.com/rds/home"

# Open S3 console
open "https://console.aws.amazon.com/s3/home"

# Open EC2 security groups
open "https://console.aws.amazon.com/ec2/v2/home"

# Open IAM policies
open "https://console.aws.amazon.com/iam/home"
```

---

## Cost Estimation (Monthly)

- **RDS db.t3.micro**: ~$15 (free tier eligible)
- **S3 Storage** (first 1TB): ~$20-30
- **Data Transfer**: ~$5-10
- **Total**: ~$50-60/month

Use AWS Pricing Calculator: https://calculator.aws/

---

## Production Considerations

Before going to production:

1. ✅ Scale RDS to `db.t3.small` or `db.t4.small`
2. ✅ Enable Multi-AZ for high availability
3. ✅ Make RDS non-public (`PubliclyAccessible=False`)
4. ✅ Enable automated backups (21 days retention)
5. ✅ Use AWS Secrets Manager for sensitive data
6. ✅ Set up CloudWatch alarms & monitoring
7. ✅ Use Application Load Balancer (ALB)
8. ✅ Enable CloudFront CDN for S3
9. ✅ Restrict security group to app server IPs only
10. ✅ Enable encryption at rest and in transit

See [AWS_DEPLOYMENT.md](../AWS_DEPLOYMENT.md#production-checklist) for full checklist.

---

## Related Documentation

- [AWS_DEPLOYMENT.md](../AWS_DEPLOYMENT.md) — Complete deployment guide
- [../README.md](../README.md) — Project overview
- [migrations/](../migrations/) — Database schema
- [services/repositories/](../services/repositories/) — Data access layer

---

## Support

For issues or questions:

1. Check logs: `tail -f logs/app.log`
2. Review [AWS_DEPLOYMENT.md#troubleshooting](../AWS_DEPLOYMENT.md#troubleshooting)
3. Check AWS CloudWatch logs in console
4. Review AWS documentation: https://docs.aws.amazon.com/

---

**Created:** 2026-03-29
