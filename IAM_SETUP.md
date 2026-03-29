# IAM Service Account Setup Guide

**SECURITY BEST PRACTICE**: Never use root AWS credentials in your application or development environment. Create an IAM service account instead.

## Why You Need This

- **Security**: Least privilege access—app has only necessary permissions
- **Auditability**: AWS logs show which IAM user performed actions
- **Revocation**: Can disable/delete credentials without affecting root account
- **Free Tier Safe**: No additional charges for IAM users

## Quick Start (3 Steps)

### Step 1: Sign in with Root (One Time)

1. Go to [AWS Console](https://console.aws.amazon.com/)
2. Sign in with your root email and password
3. Open a terminal in your project directory

### Step 2: Run IAM Setup Script

```bash
cd infinitydesignerboutique-mgmt
python scripts/setup_iam_user.py --username infinity-app-user --region ap-south-1
```

**Expected Output:**
```
✓ IAM user created: infinity-app-user
✓ Policy attached to infinity-app-user: InfinityAppPolicy

===========================================================
✓ IAM USER SETUP COMPLETE
===========================================================

📋 CREDENTIALS (save these securely):

  Access Key ID:     AKIAIOSFODNN7EXAMPLE
  Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

  ⚠️  IMPORTANT: Save these securely!
```

### Step 3: Configure AWS CLI with Service Account

```bash
aws configure --profile infinity-app
```

When prompted:
```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: ap-south-1
Default output format [None]: json
```

#### Verify Setup

```bash
aws sts get-caller-identity --profile infinity-app
```

Expected:
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/infinity-app-user"
}
```

---

## Manual Setup (If Script Fails)

If the script doesn't work, follow these manual steps:

### 1. Create IAM User in AWS Console

1. Go to [IAM Users Console](https://console.aws.amazon.com/iamv2/home#/users)
2. Click **Create user**
3. **User name**: `infinity-app-user`
4. Click **Next**
5. Click **Attach policies directly** (we'll use inline policy)
6. Click **Next** → **Create user**

### 2. Create Access Keys

1. In the IAM Users list, click `infinity-app-user`
2. Go to **Security credentials** tab
3. Scroll to **Access keys** section
4. Click **Create access key**
5. Select **Application running outside AWS** → **Next**
6. Add description: `Infinity Designer Boutique App`
7. Click **Create access key**
8. **⚠️ SAVE THESE IMMEDIATELY** (you can only see them once):
   - Access Key ID
   - Secret Access Key
9. Download CSV or copy both values

### 3. Add Permissions (Inline Policy)

1. Still on `infinity-app-user` page, go to **Permissions** tab
2. Click **Add permissions** → **Create inline policy**
3. Choose **JSON** editor
4. Paste this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RDSAccess",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters",
        "rds:DescribeDBParameterGroups"
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
        "s3:ListBucket",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::infinity-boutique-files*",
        "arn:aws:s3:::infinity-boutique-files*/*"
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
      "Sid": "EC2SecurityGroupView",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

5. Click **Create policy**
6. Policy name: `InfinityAppPolicy` → **Create policy**

---

## Using Service Credentials in Your App

### Option A: AWS CLI Profile (Recommended)

After `aws configure --profile infinity-app`, update `.env`:

```env
# .env
AWS_PROFILE=infinity-app
AWS_REGION=ap-south-1
APP_DB_PROVIDER=postgres
APP_STORAGE_PROVIDER=s3
```

Then run app:
```bash
export AWS_PROFILE=infinity-app
python app.py
```

### Option B: Direct Credentials

Update `.env` with access keys:

```env
# .env (less secure - use Option A if possible)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=ap-south-1
APP_DB_PROVIDER=postgres
APP_STORAGE_PROVIDER=s3
```

### Option C: Environment Variables

```bash
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
export AWS_REGION="ap-south-1"
python app.py
```

---

## Now Run AWS Setup

With your service account credentials configured, run the main setup:

```bash
aws configure --profile infinity-app  # Already done above

# Create AWS resources (RDS, S3, security groups)
python scripts/aws_setup.py \
  --project-name infinity-boutique \
  --region ap-south-1 \
  --profile infinity-app
```

This will use your service account instead of root.

---

## Security Checklist

- ✅ IAM user created (not using root credentials)
- ✅ Access keys generated
- ✅ Inline policy attached (specific permissions)
- ✅ AWS CLI configured with service credentials
- ✅ Verified with `aws sts get-caller-identity`
- ✅ Credentials stored securely (.env or AWS credentials file)

---

## Next Steps

1. ✅ Complete this IAM setup
2. Run `python scripts/aws_setup.py` to create RDS + S3 (5 min)
3. Wait for RDS initialization (5-10 min)
4. Run `python scripts/aws_check.py` to verify resources
5. Deploy app with `APP_DB_PROVIDER=postgres`

---

## Troubleshooting

### "LimitExceeded" when creating access keys

**Problem**: IAM user already has 2 access keys

**Solution**:
1. Go to IAM Users Console
2. Click `infinity-app-user`
3. Go to **Security credentials**
4. Deactivate or delete old access key (mark as Inactive first)
5. Try again

###  "User: arn:aws:iam::... is not authorized"

**Problem**: Service account doesn't have permission for action

**Solution**:
1. Update the inline policy with broader permissions
2. Or create a new user by deleting and rerunning setup script

### "InvalidUserID.NotFound" in aws_setup.py

**Problem**: Using root credentials but script expects service account

**Solution**: Run IAM setup first (this guide), then aws_setup.py will work

### Can't see Secret Access Key again

**Problem**: You didn't save it immediately after creation

**Solution**: 
1. Delete the access key
2. Create a new one
3. Save immediately to secure location

---

## Removing IAM User (If Needed)

To delete the service account:

```bash
# Delete access keys first
aws iam delete-access-key --user-name infinity-app-user \
  --access-key-id AKIAIOSFODNN7EXAMPLE

# Delete inline policies
aws iam delete-user-policy --user-name infinity-app-user \
  --policy-name InfinityAppPolicy

# Delete user
aws iam delete-user --user-name infinity-app-user
```

---

## Additional Resources

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [IAM Policies Documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)
