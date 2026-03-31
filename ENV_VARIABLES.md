# Environment Variables Reference

This project now runs on PostgreSQL + AWS S3 only.

## Core Flask

| Variable | Required | Default | Example |
|---|---|---|---|
| `FLASK_ENV` | Yes | - | `development`, `production` |
| `FLASK_SECRET_KEY` | Yes | - | 64+ hex chars |
| `FLASK_DEBUG` | No | `False` | `True`, `False` |
| `PORT` | No | `5000` | `5000` |

## Session

| Variable | Required | Default | Example |
|---|---|---|---|
| `SESSION_LIFETIME_SECONDS` | No | `28800` | `28800` |

## PostgreSQL

| Variable | Required | Default | Example |
|---|---|---|---|
| `POSTGRES_HOST` | Yes | - | `localhost`, `db.example.rds.amazonaws.com` |
| `POSTGRES_PORT` | No | `5432` | `5432` |
| `POSTGRES_DB` | Yes | - | `infinity_boutique` |
| `POSTGRES_USER` | Yes | - | `dbadmin` |
| `POSTGRES_PASSWORD` | Yes | - | `StrongPassword123` |
| `POSTGRES_SSLMODE` | No | `require` | `require`, `disable` |
| `POSTGRES_CONNECT_TIMEOUT` | No | `10` | `10` |

## AWS S3

| Variable | Required | Default | Example |
|---|---|---|---|
| `AWS_REGION` | Yes | - | `ap-south-1` |
| `AWS_S3_BUCKET` | Yes | - | `infinity-boutique-files-ap-south-1` |
| `AWS_ACCESS_KEY_ID` | No | - | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | No | - | `...` |
| `AWS_PROFILE` | No | - | `infinity-app` |

## App and Logging

| Variable | Required | Default | Example |
|---|---|---|---|
| `BOUTIQUE_NAME` | No | `Infinity Designer Boutique` | `Infinity Designer Boutique` |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | No | `*` | `https://yourdomain.com` |

## Root Admin Bootstrap

| Variable | Required | Default | Example |
|---|---|---|---|
| `ROOT_ADMIN_FULL_NAME` | No | `Root Admin` | `Root Admin` |
| `ROOT_ADMIN_PHONE` | No | `9999999999` | `9999999999` |
| `ROOT_ADMIN_PIN` | No | `0000` | `0000` |

## Minimal Local Example

```bash
FLASK_ENV=development
FLASK_SECRET_KEY=replace-with-strong-key
FLASK_DEBUG=True
PORT=5000
SESSION_LIFETIME_SECONDS=28800

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=infinity_boutique
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SSLMODE=disable
POSTGRES_CONNECT_TIMEOUT=10

AWS_REGION=ap-south-1
AWS_S3_BUCKET=infinity-boutique-files-ap-south-1

BOUTIQUE_NAME=Infinity Designer Boutique
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Notes

- `APP_DB_PROVIDER` and `APP_STORAGE_PROVIDER` are no longer used.
- Firebase/Firestore credentials are no longer used.
- Use `python scripts/aws_manage.py setup ...` to generate `.env.aws` for AWS deployments.
