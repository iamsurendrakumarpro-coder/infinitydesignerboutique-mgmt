# AWS Migration Runbook (Free Tier First)

## Goal
Migrate this Flask app from Firebase to AWS for hosting, database, file storage, and operations with minimal downtime and minimal monthly cost.

## Recommended AWS Stack
- Hosting: EC2 t3.micro (Amazon Linux 2023) + Nginx + Gunicorn + systemd
- Database: Amazon RDS PostgreSQL (db.t3.micro, free tier)
- File storage: Amazon S3 (private bucket) + presigned URLs
- Secrets: AWS Systems Manager Parameter Store (or Secrets Manager)
- Logs/monitoring: CloudWatch Agent + CloudWatch Logs + alarms
- DNS/TLS: Route 53 + ACM certificate (TLS via Nginx)

## Why This Stack
- Cheapest stable path on AWS free tier.
- Easy to run Flask app without major platform lock-in.
- PostgreSQL provides strong querying and transaction support for payroll/settlement logic.
- S3 handles proofs/receipts/gallery safely and cheaply.

## Current Firebase Coupling (Codebase)
- Core DB client and storage client: utils/firebase_client.py
- App startup eager DB init: app.py
- Firestore used across most service modules (auth, users, attendance, financial, overtime, settlements, dashboard, leave)
- Firebase Storage used in user and financial flows (proofs, gallery, receipts)

## Newly Added Changes To Include In Migration Scope
These are currently implemented in the app and must be carried into AWS migration planning:
- Leave management domain:
   - API routes: modules/leave/routes.py
   - Business logic: services/leave_service.py
   - Staff UI: templates/staff/leave.html
- API contract and middleware:
   - Standard API response envelope: middleware/response.py
   - Security headers middleware: middleware/security.py
   - Rate limiting middleware: middleware/rate_limit.py
- Error-message standardization:
   - Python constants: utils/error_messages.py
   - Frontend constants/helpers: static/js/error-messages.js
- Ongoing UI refactors in admin/staff templates (non-blocking for infra migration, but relevant for smoke tests and QA).

## Migration Impact Of New Changes
- Leave module:
   - Add leave_requests table and migration mapping in PostgreSQL plan.
   - Add leave endpoints to cutover smoke tests and rollback checks.
- Standard API envelope:
   - Preserve response format parity during DB provider switch (Firebase -> Postgres).
   - Add contract tests to ensure success/error/meta fields remain stable.
- Security headers:
   - Keep app-level headers and ensure Nginx does not conflict/override unexpectedly.
   - Validate CSP/connect-src after moving assets/storage endpoints.
- Rate limiting:
   - Current in-memory limiter is single-instance only; move to Redis-backed store for multi-instance AWS deployments.
   - Keep auth endpoints on stricter policies during and after cutover.
- Error messaging:
   - Keep standardized user messages in both backend and frontend post-migration.
   - Add regression checks for high-risk flows (login, attendance, settlements, onboarding upload).

## Migration Strategy (Phased)

### Phase 0: Foundation (1-2 days)
1. Create AWS resources:
   - EC2 instance (public subnet)
   - RDS PostgreSQL instance (private or public with strict SG)
   - S3 buckets:
     - boutique-app-media (proofs/gallery/receipts)
     - optional boutique-app-backups
2. IAM setup:
   - EC2 role with S3 access limited to media bucket
   - CloudWatch logs permissions
3. Security groups:
   - EC2: allow 80/443 from internet, 22 restricted to your IP
   - RDS: allow 5432 only from EC2 SG

### Phase 1: Code Abstraction (2-4 days)
1. Introduce provider interfaces:
   - DB provider: firebase, postgres
   - Storage provider: firebase, s3
2. Keep existing behavior unchanged by default (firebase provider).
3. Add AWS implementations in parallel:
   - utils/db/postgres_client.py
   - utils/storage/s3_client.py
4. Add feature flag envs:
   - APP_DB_PROVIDER=firebase|postgres
   - APP_STORAGE_PROVIDER=firebase|s3
5. Add API contract checks:
   - Validate middleware/response envelope compatibility before and after provider switches.
6. Prepare scalable rate-limit backend:
   - Replace in-memory limiter backend with Redis in AWS environments.

### Phase 2: Schema + Data Migration (2-4 days)
1. Create PostgreSQL schema from Firestore model.
2. Write one-time migration script:
   - Read from Firestore
   - Transform and insert into PostgreSQL
3. Migrate media objects:
   - Copy from Firebase Storage to S3
   - Preserve key paths for compatibility where possible
4. Validate counts and totals:
   - staff, attendance logs, financial requests, overtime, settlements, leave

### Phase 3: Cutover (1 day)
1. Deploy code with dual-read verification in staging.
2. Freeze writes briefly (maintenance window).
3. Final delta migration.
4. Switch env flags to postgres + s3.
5. Smoke test critical flows:
   - login
   - attendance in/out
   - request/approve expense
   - overtime
   - settlement generation + settle
   - leave apply/approve/cancel/list
   - staff onboarding with govt proof upload
   - API error envelope + user-friendly error surfaces
   - security headers + CSP behavior

### Phase 4: Post-Cutover (1-2 days)
1. Monitor errors and DB performance.
2. Remove Firebase dependencies after a stable period.
3. Archive migration logs and create rollback snapshot references.

## Proposed PostgreSQL Core Tables
- users_admin
- staff
- attendance_logs
- financial_requests
- overtime_requests
- settlements
- leave_requests
- work_gallery
- audit_logs

Notes:
- Use UUID PKs where IDs are currently string IDs.
- Keep created_at / updated_at as timestamptz with DB defaults.
- Add indexes for weekly/monthly settlement filters and staff/date lookups.

## S3 Design
- Bucket: boutique-app-media (private)
- Key prefixes:
  - govt_proofs/{staff_id}/{proof_id}.{ext}
  - gallery/{staff_id}/{image_id}.{ext}
  - receipts/{request_id}/{file_id}.{ext}
- Access model:
  - Never public-read by default
  - Serve via short-lived presigned URLs

## Environment Variables (Target)
- APP_DB_PROVIDER=postgres
- APP_STORAGE_PROVIDER=s3
- POSTGRES_HOST=
- POSTGRES_PORT=5432
- POSTGRES_DB=
- POSTGRES_USER=
- POSTGRES_PASSWORD=
- AWS_REGION=ap-south-1
- AWS_S3_BUCKET=boutique-app-media
- AWS_ACCESS_KEY_ID= (optional if instance role used)
- AWS_SECRET_ACCESS_KEY= (optional if instance role used)

## Free-Tier Cost Guardrails
- Prefer one EC2 and one RDS instance only.
- Avoid ALB initially (adds cost); use Nginx directly on EC2.
- Keep S3 lifecycle rules for old files/backups.
- Set billing alarms at low thresholds (for example, 5 USD, 10 USD).

## Rollback Plan
- Keep Firebase as source of truth until cutover complete.
- Take RDS snapshot before go-live.
- If severe issue after cutover:
  - switch APP_DB_PROVIDER and APP_STORAGE_PROVIDER back to firebase
  - redeploy app

## Immediate Next Actions
1. Build PostgreSQL schema and repository layer for: users, attendance, financial, overtime, settlements, leave.
2. Implement Firestore -> PostgreSQL migration scripts including leave_requests and settlement metadata.
3. Add Redis-backed rate limit configuration for AWS and keep in-memory fallback for local dev.
4. Add response-envelope regression tests for auth, attendance, settlements, leave.
5. Execute staged DB+S3 smoke tests and document rollback checkpoints.

---
If you want, next step I can start Phase 1 now and implement provider abstractions + S3 storage integration first (keeping Firestore live until DB migration is ready).
