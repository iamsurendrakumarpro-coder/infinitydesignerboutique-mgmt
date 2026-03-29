# Environment Variables Reference

Complete reference for all environment variables used in the application.

## Quick Reference

### Deployment Mode (Choose One)

```bash
# Local Development with Firestore
APP_DB_PROVIDER=firebase
APP_STORAGE_PROVIDER=firebase

# AWS Production with Postgres & S3
APP_DB_PROVIDER=postgres
APP_STORAGE_PROVIDER=s3
```

---

## Flask Configuration

| Variable | Required | Default | Example | Purpose |
|---|---|---|---|---|
| `FLASK_ENV` | ✅ | — | `development`, `production` | Execution environment |
| `FLASK_SECRET_KEY` | ✅ | — | `abc123def456...` (32+ chars) | Session cookie signing |
| `FLASK_DEBUG` | ❌ | `False` | `True`, `False` | Debug mode (dev only) |
| `PORT` | ❌ | `5000` | `5000`, `8080` | Server port |

**Examples:**

Development:
```bash
FLASK_ENV=development
FLASK_SECRET_KEY=dev-secret-key-not-secure
FLASK_DEBUG=True
PORT=5000
```

Production:
```bash
FLASK_ENV=production
FLASK_SECRET_KEY=<32+ char random string>
FLASK_DEBUG=False
PORT=5000
```

**Generate Secret Key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Session Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SESSION_LIFETIME_SECONDS` | ❌ | `28800` | How long login lasts (8 hours) |

**Example:**
```bash
SESSION_LIFETIME_SECONDS=28800    # 8 hours
SESSION_LIFETIME_SECONDS=86400    # 1 day
SESSION_LIFETIME_SECONDS=3600     # 1 hour
```

---

## Firestore Configuration (App_DB_Provider=firebase)

| Variable | Required | Default | Example | Purpose |
|---|---|---|---|---|
| `FIREBASE_CREDENTIALS_PATH` | ✅ | — | `firebase-credentials.json` | Path to service account JSON |
| `FIREBASE_PROJECT_ID` | ✅ | — | `my-firebase-project` | Firestore project ID |
| `FIREBASE_STORAGE_BUCKET` | ✅ | — | `my-project.appspot.com` | Storage bucket for files |

**Example:**
```bash
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=infinity-designer-boutique
FIREBASE_STORAGE_BUCKET=infinity-designer-boutique.appspot.com
```

**Getting Values:**
1. Go to Firebase Console → Settings → Project Settings
2. Find `Project ID` field
3. Download service account key JSON file
4. Save as `firebase-credentials.json` in project root

---

## PostgreSQL Configuration (APP_DB_PROVIDER=postgres)

| Variable | Required | Default | Example | Purpose |
|---|---|---|---|---|
| `POSTGRES_HOST` | ✅ | — | `localhost`, `db.example.rds.amazonaws.com` | Database host |
| `POSTGRES_PORT` | ✅ | `5432` | `5432` | Database port |
| `POSTGRES_DB` | ✅ | — | `infinity_boutique` | Database name |
| `POSTGRES_USER` | ✅ | — | `dbadmin` | Database user |
| `POSTGRES_PASSWORD` | ✅ | — | `SecureP@ssw0rd123` | Database password |

**Local Development Example:**
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=infinity_boutique_dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

**AWS RDS Production Example:**
```bash
POSTGRES_HOST=infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=infinity_boutique
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=<secure-password>
```

**Connection String (for reference):**
```
postgresql://user:password@host:port/database
```

---

## AWS S3 Configuration (APP_STORAGE_PROVIDER=s3)

| Variable | Required | Default | Example | Purpose |
|---|---|---|---|---|
| `AWS_REGION` | ✅ | — | `ap-south-1`, `us-east-1` | AWS region |
| `AWS_S3_BUCKET` | ✅ | — | `my-bucket-name` | S3 bucket for uploads |
| `AWS_ACCESS_KEY_ID` | ❌ | — | `AKIA...` | AWS access key (if not using IAM roles) |
| `AWS_SECRET_ACCESS_KEY` | ❌ | — | `wJalr...` | AWS secret key (if not using IAM roles) |

**Example (with Environment Credentials):**
```bash
AWS_REGION=ap-south-1
AWS_S3_BUCKET=infinity-boutique-files-ap-south-1
```

**Example (with explicit credentials):**
```bash
AWS_REGION=ap-south-1
AWS_S3_BUCKET=infinity-boutique-files-ap-south-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Getting AWS S3 Bucket Name:**
```bash
python scripts/aws_check.py --project-name infinity-boutique --region ap-south-1
```

---

## Application Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BOUTIQUE_NAME` | ❌ | `Infinity Designer Boutique` | Display name in UI |

**Example:**
```bash
BOUTIQUE_NAME="Infinity Designer Boutique - Delhi"
```

---

## Logging Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LOG_LEVEL` | ❌ | `INFO` | Verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL |

**Recommended by Environment:**

Development:
```bash
LOG_LEVEL=DEBUG
```

Production:
```bash
LOG_LEVEL=WARNING    # Only warnings and errors
# or
LOG_LEVEL=INFO       # General info + warnings + errors
```

---

## CORS Configuration

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `CORS_ORIGINS` | ❌ | `http://localhost:*` | Allowed frontend origins (comma-separated) |

**Examples:**

Local Development:
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Production:
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Multiple Origins:**
```bash
CORS_ORIGINS=https://api.example.com,https://app.example.com,https://admin.example.com
```

---

## Root Admin Seeding

Only used during initial setup (one-time):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ROOT_ADMIN_FULL_NAME` | ❌ | `Root Admin` | Initial admin name |
| `ROOT_ADMIN_PHONE` | ❌ | `9999999999` | Initial admin phone |
| `ROOT_ADMIN_PIN` | ❌ | `0000` | Initial admin PIN (4 digits) |

⚠️ **Remove or update after first login!**

```bash
ROOT_ADMIN_FULL_NAME="Amit Kumar"
ROOT_ADMIN_PHONE=9876543210
ROOT_ADMIN_PIN=1234
```

---

## Complete Configuration Examples

### Local Development (.env.local)

```bash
# Flask
FLASK_ENV=development
FLASK_SECRET_KEY=dev-key-not-for-production
FLASK_DEBUG=True
PORT=5000

# Session
SESSION_LIFETIME_SECONDS=86400

# Firestore
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=infinity-designer-boutique
FIREBASE_STORAGE_BUCKET=infinity-designer-boutique.appspot.com

# Providers
APP_DB_PROVIDER=firebase
APP_STORAGE_PROVIDER=firebase

# App
BOUTIQUE_NAME=Infinity Designer Boutique
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Root Admin
ROOT_ADMIN_FULL_NAME=Root Admin
ROOT_ADMIN_PHONE=9999999999
ROOT_ADMIN_PIN=0000
```

### AWS Production (.env)

```bash
# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=<long-random-32-char-string>
FLASK_DEBUG=False
PORT=5000

# Session
SESSION_LIFETIME_SECONDS=28800

# Firestore (for fallback only)
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=infinity-designer-boutique
FIREBASE_STORAGE_BUCKET=infinity-designer-boutique.appspot.com

# Providers
APP_DB_PROVIDER=postgres
APP_STORAGE_PROVIDER=s3

# PostgreSQL
POSTGRES_HOST=infinity-boutique-db.xxxxx.ap-south-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=infinity_boutique
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=<secure-password>

# AWS S3
AWS_REGION=ap-south-1
AWS_S3_BUCKET=infinity-boutique-files-ap-south-1

# App
BOUTIQUE_NAME=Infinity Designer Boutique
LOG_LEVEL=INFO
CORS_ORIGINS=https://infinitydesigner.com,https://www.infinitydesigner.com

# Root Admin
ROOT_ADMIN_FULL_NAME=Admin User
ROOT_ADMIN_PHONE=9876543210
ROOT_ADMIN_PIN=1234
```

### Docker Production

```bash
# Use secrets instead of .env for sensitive data
# Example with Docker environment variables:

FLASK_ENV=production
FLASK_SECRET_KEY=${FLASK_SECRET_KEY}   # From Docker secret
APP_DB_PROVIDER=postgres
POSTGRES_HOST=rds-endpoint
POSTGRES_DB=infinity_boutique
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=${DB_PASSWORD}       # From Docker secret
AWS_REGION=ap-south-1
AWS_S3_BUCKET=bucket-name
LOG_LEVEL=INFO
```

---

## Loading Environment Variables

### Method 1: .env File (Development)

```bash
# .gitignore should include .env
echo ".env" >> .gitignore

# Create .env file
cp .env.example .env

# Edit .env with your values
nano .env

# Shell automatically loads .env via python-dotenv
python app.py
```

### Method 2: Export Variables (Development/Testing)

```bash
export FLASK_ENV=development
export POSTGRES_HOST=localhost
export POSTGRES_DB=infinity_boutique

python app.py
```

### Method 3: AWS Systems Manager Parameter Store (Production)

```bash
# Store in Parameter Store
aws ssm put-parameter \
  --name /infinity-boutique/POSTGRES_PASSWORD \
  --value "your-password" \
  --type SecureString

# Retrieve in application
import boto3
ssm = boto3.client("ssm")
password = ssm.get_parameter(
    Name="/infinity-boutique/POSTGRES_PASSWORD",
    WithDecryption=True
)["Parameter"]["Value"]
```

### Method 4: Docker Environment Variables

```dockerfile
# Dockerfile
ENV FLASK_ENV=production
ENV APP_DB_PROVIDER=postgres

# docker run with --env-file
docker run --env-file .env.prod myimage
```

---

## Validation Checklist

Before deploying:

- [ ] `FLASK_SECRET_KEY` is 32+ characters and random
- [ ] `FLASK_ENV` matches deployment environment
- [ ] `POSTGRES_HOST` is accessible from app server
- [ ] `POSTGRES_PASSWORD` is secure and not the default
- [ ] `AWS_S3_BUCKET` exists and app has access
- [ ] `CORS_ORIGINS` includes your frontend domain
- [ ] `LOG_LEVEL` is appropriate for environment
- [ ] Firebase credentials are NOT in .env (use path instead)
- [ ] `.env` file is in `.gitignore`
- [ ] All required variables are set

---

## Migration Path

**From Firestore to Postgres:**

```bash
# Step 1: Run setup script
python scripts/aws_setup.py --project-name my-project

# Step 2: Update .env
cp .env.aws .env
nano .env  # Update CORS_ORIGINS, etc.

# Step 3: Create tables
python scripts/init_db.py

# Step 4: Migrate data
python scripts/migrate_firestore_to_postgres.py

# Step 5: Switch providers
# In .env, change:
# APP_DB_PROVIDER=postgres
# APP_STORAGE_PROVIDER=s3

# Step 6: Test application
python app.py

# Step 7: Verify data integrity
python scripts/verify_migration.py

# Step 8: Deploy
gunicorn app:app --bind 0.0.0.0:5000
```

---

## Troubleshooting

### "Missing Required Environment Variable"

```bash
# Check which variables are set
env | grep -E "FLASK|POSTGRES|AWS"

# Load .env manually
export $(cat .env | xargs)
```

### Variables Not Loaded from .env

**Ensure you have python-dotenv:**
```bash
pip install python-dotenv
```

**In app.py:**
```python
from dotenv import load_dotenv
load_dotenv()
```

### TypeError: unsupported operand type(s)

If you get type errors, ensure environment variables are correct type:

```python
PORT = int(os.getenv("PORT", "5000"))  # Convert to int
SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME_SECONDS", "28800"))
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"  # Convert to bool
```

---

## Security Best Practices

1. ✅ **Never commit `.env`** - Always add to `.gitignore`
2. ✅ **Use strong passwords** - Minimum 16 characters, mix of types
3. ✅ **Rotate secrets** - Change `FLASK_SECRET_KEY` periodically
4. ✅ **Use AWS Secrets Manager** - For production credentials
5. ✅ **Restrict permissions** - Limit who can access `.env` file
6. ✅ **Use environment-specific files** - `.env.local`, `.env.prod`
7. ✅ **Log rotation** - Don't log sensitive values
8. ✅ **Audit access** - Monitor who accesses .env files

---

## Related Documentation

- [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) - AWS setup guide
- [scripts/README.md](scripts/README.md) - Script documentation
- [.env.example](.env.example) - Template file
- [config.py](config.py) - Configuration loading

---

**Last Updated:** 2026-03-29
