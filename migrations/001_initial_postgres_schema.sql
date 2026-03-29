-- Initial PostgreSQL schema for Firebase -> AWS RDS migration.
-- This schema intentionally keeps Firestore string IDs as TEXT primary keys
-- so one-time migration can preserve existing references without remapping IDs.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS admins (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    is_root BOOLEAN NOT NULL DEFAULT FALSE,
    is_first_login BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS staff (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL UNIQUE,
    designation TEXT,
    joining_date DATE,
    standard_login_time TEXT,
    standard_logout_time TEXT,
    emergency_contact TEXT,
    salary_type TEXT NOT NULL DEFAULT 'weekly' CHECK (salary_type IN ('weekly', 'monthly')),
    settlement_cycle TEXT NOT NULL DEFAULT 'weekly' CHECK (settlement_cycle IN ('weekly', 'monthly')),
    weekly_salary NUMERIC(12,2),
    monthly_salary NUMERIC(12,2),
    daily_salary NUMERIC(12,2),
    skills TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deactivated')),
    pin_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',
    is_first_login BOOLEAN NOT NULL DEFAULT TRUE,
    govt_proof JSONB,
    created_by TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS staff_work_gallery (
    image_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    image_url TEXT,
    storage_path TEXT,
    caption TEXT,
    uploaded_by TEXT,
    uploaded_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS staff_performance_logs (
    log_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by TEXT,
    created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS attendance_logs (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    punch_in TIMESTAMPTZ,
    punch_out TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('in', 'out')),
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE (user_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS financial_requests (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('shop_expense', 'personal_advance')),
    category TEXT,
    amount NUMERIC(12,2) NOT NULL,
    receipt_gcs_path TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    admin_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS overtime_records (
    record_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    staff_name TEXT,
    full_name TEXT,
    record_date DATE,
    total_worked_minutes INTEGER NOT NULL DEFAULT 0,
    overtime_minutes INTEGER NOT NULL DEFAULT 0,
    hourly_rate NUMERIC(12,2) NOT NULL DEFAULT 0,
    calculated_payout NUMERIC(12,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    full_name TEXT,
    designation TEXT,
    salary_type TEXT CHECK (salary_type IN ('weekly', 'monthly')),
    settlement_cycle TEXT NOT NULL DEFAULT 'weekly' CHECK (settlement_cycle IN ('weekly', 'monthly')),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    weekly_salary NUMERIC(12,2),
    monthly_salary NUMERIC(12,2),
    daily_salary NUMERIC(12,2),
    days_present INTEGER,
    base_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    overtime_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    expenses NUMERIC(12,2) NOT NULL DEFAULT 0,
    advances NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_payable NUMERIC(12,2) NOT NULL DEFAULT 0,
    hours_worked NUMERIC(10,2) NOT NULL DEFAULT 0,
    ot_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    carry_forward_in NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount_settled NUMERIC(12,2) NOT NULL DEFAULT 0,
    carry_forward NUMERIC(12,2) NOT NULL DEFAULT 0,
    settlement_status TEXT NOT NULL DEFAULT 'pending' CHECK (settlement_status IN ('pending', 'partial', 'settled')),
    generated_by TEXT,
    settled_by TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE (user_id, week_start, week_end, settlement_cycle)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL CHECK (leave_type IN ('half_day', 'full_day', 'multiple_days')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    half_day_period TEXT CHECK (half_day_period IN ('morning', 'afternoon')),
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    admin_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    total_days NUMERIC(8,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS app_settings (
    config_type TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    updated_by TEXT,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS migration_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(status);
CREATE INDEX IF NOT EXISTS idx_staff_joining_date ON staff(joining_date);

CREATE INDEX IF NOT EXISTS idx_gallery_user_uploaded ON staff_work_gallery(user_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_perf_logs_user_created ON staff_performance_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_logs(user_id, attendance_date DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_logs(attendance_date DESC);

CREATE INDEX IF NOT EXISTS idx_financial_user_status_date ON financial_requests(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_financial_type_status ON financial_requests(type, status);

CREATE INDEX IF NOT EXISTS idx_overtime_user_date ON overtime_records(user_id, record_date DESC);
CREATE INDEX IF NOT EXISTS idx_overtime_status ON overtime_records(status);

CREATE INDEX IF NOT EXISTS idx_settlements_user_week_end ON settlements(user_id, week_end DESC);
CREATE INDEX IF NOT EXISTS idx_settlements_cycle_period ON settlements(settlement_cycle, week_start, week_end);
CREATE INDEX IF NOT EXISTS idx_settlements_status ON settlements(settlement_status);

CREATE INDEX IF NOT EXISTS idx_leave_user_status ON leave_requests(user_id, status, start_date DESC);
CREATE INDEX IF NOT EXISTS idx_leave_date_span ON leave_requests(start_date, end_date);

COMMIT;