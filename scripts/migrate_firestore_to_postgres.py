"""
One-time Firestore -> PostgreSQL migration script (draft).

Scope migrated:
- admins
- staff
- staff/{user_id}/work_gallery
- staff/{user_id}/performance_logs
- attendance/{user_id}/records
- financial_requests
- overtime_records
- settlements
- leave_requests
- settings

Usage examples:
    python scripts/migrate_firestore_to_postgres.py --dry-run
    python scripts/migrate_firestore_to_postgres.py --apply-schema
    python scripts/migrate_firestore_to_postgres.py

Environment variables required:
    FIREBASE_CREDENTIALS_PATH
    FIREBASE_PROJECT_ID
    POSTGRES_HOST
    POSTGRES_PORT
    POSTGRES_DB
    POSTGRES_USER
    POSTGRES_PASSWORD
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

from utils.firebase_client import get_firestore


ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT_DIR / "migrations" / "001_initial_postgres_schema.sql"


@dataclass
class MigrationStats:
    admins: int = 0
    staff: int = 0
    gallery: int = 0
    performance_logs: int = 0
    attendance: int = 0
    financial_requests: int = 0
    overtime_records: int = 0
    settlements: int = 0
    leave_requests: int = 0
    settings: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "admins": self.admins,
            "staff": self.staff,
            "gallery": self.gallery,
            "performance_logs": self.performance_logs,
            "attendance": self.attendance,
            "financial_requests": self.financial_requests,
            "overtime_records": self.overtime_records,
            "settlements": self.settlements,
            "leave_requests": self.leave_requests,
            "settings": self.settings,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate Firestore collections into PostgreSQL.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read Firestore and print counts only; do not write to PostgreSQL.",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Execute migrations/001_initial_postgres_schema.sql before data migration.",
    )
    return parser.parse_args()


def load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def to_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    if hasattr(value, "to_datetime"):
        try:
            return value.to_datetime()
        except Exception:
            return None
    return None


def to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def safe_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=require_env("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=require_env("POSTGRES_DB"),
        user=require_env("POSTGRES_USER"),
        password=require_env("POSTGRES_PASSWORD"),
    )


def apply_schema(conn: psycopg2.extensions.connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def migrate_admins(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("admins").stream():
        data = doc.to_dict() or {}
        cur.execute(
            """
            INSERT INTO admins (
                user_id, full_name, phone_number, pin_hash, role, is_root,
                is_first_login, created_by, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                phone_number = EXCLUDED.phone_number,
                pin_hash = EXCLUDED.pin_hash,
                role = EXCLUDED.role,
                is_root = EXCLUDED.is_root,
                is_first_login = EXCLUDED.is_first_login,
                created_by = EXCLUDED.created_by,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("user_id") or doc.id,
                data.get("full_name", ""),
                data.get("phone_number", ""),
                data.get("pin_hash", ""),
                data.get("role", "admin"),
                bool(data.get("is_root", False)),
                bool(data.get("is_first_login", True)),
                safe_text(data.get("created_by")),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.admins += 1


def migrate_staff_and_subcollections(db, cur, stats: MigrationStats) -> None:
    for staff_doc in db.collection("staff").stream():
        data = staff_doc.to_dict() or {}
        skills = data.get("skills", [])
        if not isinstance(skills, list):
            skills = []

        govt_proof = data.get("govt_proof")
        govt_proof_json = Json(govt_proof) if isinstance(govt_proof, dict) else None

        cur.execute(
            """
            INSERT INTO staff (
                user_id, full_name, phone_number, designation, joining_date,
                standard_login_time, standard_logout_time, emergency_contact,
                salary_type, settlement_cycle, weekly_salary, monthly_salary,
                daily_salary, skills, status, pin_hash, role, is_first_login,
                govt_proof, created_by, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (user_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                phone_number = EXCLUDED.phone_number,
                designation = EXCLUDED.designation,
                joining_date = EXCLUDED.joining_date,
                standard_login_time = EXCLUDED.standard_login_time,
                standard_logout_time = EXCLUDED.standard_logout_time,
                emergency_contact = EXCLUDED.emergency_contact,
                salary_type = EXCLUDED.salary_type,
                settlement_cycle = EXCLUDED.settlement_cycle,
                weekly_salary = EXCLUDED.weekly_salary,
                monthly_salary = EXCLUDED.monthly_salary,
                daily_salary = EXCLUDED.daily_salary,
                skills = EXCLUDED.skills,
                status = EXCLUDED.status,
                pin_hash = EXCLUDED.pin_hash,
                role = EXCLUDED.role,
                is_first_login = EXCLUDED.is_first_login,
                govt_proof = EXCLUDED.govt_proof,
                created_by = EXCLUDED.created_by,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("user_id") or staff_doc.id,
                data.get("full_name", ""),
                data.get("phone_number", ""),
                safe_text(data.get("designation")),
                to_date(data.get("joining_date")),
                safe_text(data.get("standard_login_time")),
                safe_text(data.get("standard_logout_time")),
                safe_text(data.get("emergency_contact")),
                data.get("salary_type", "weekly"),
                data.get("settlement_cycle", data.get("salary_type", "weekly")),
                to_float(data.get("weekly_salary"), default=0.0) if data.get("weekly_salary") is not None else None,
                to_float(data.get("monthly_salary"), default=0.0) if data.get("monthly_salary") is not None else None,
                to_float(data.get("daily_salary"), default=0.0) if data.get("daily_salary") is not None else None,
                skills,
                data.get("status", "active"),
                data.get("pin_hash", ""),
                data.get("role", "staff"),
                bool(data.get("is_first_login", True)),
                govt_proof_json,
                safe_text(data.get("created_by")),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.staff += 1

        staff_user_id = data.get("user_id") or staff_doc.id

        for gallery_doc in db.collection("staff").document(staff_user_id).collection("work_gallery").stream():
            g = gallery_doc.to_dict() or {}
            cur.execute(
                """
                INSERT INTO staff_work_gallery (
                    image_id, user_id, image_url, storage_path, caption, uploaded_by, uploaded_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    image_url = EXCLUDED.image_url,
                    storage_path = EXCLUDED.storage_path,
                    caption = EXCLUDED.caption,
                    uploaded_by = EXCLUDED.uploaded_by,
                    uploaded_at = EXCLUDED.uploaded_at
                """,
                (
                    g.get("image_id") or gallery_doc.id,
                    staff_user_id,
                    safe_text(g.get("image_url")),
                    safe_text(g.get("storage_path")),
                    safe_text(g.get("caption")),
                    safe_text(g.get("uploaded_by")),
                    to_ts(g.get("uploaded_at")),
                ),
            )
            stats.gallery += 1

        for perf_doc in db.collection("staff").document(staff_user_id).collection("performance_logs").stream():
            p = perf_doc.to_dict() or {}
            cur.execute(
                """
                INSERT INTO staff_performance_logs (
                    log_id, user_id, note, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (log_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    note = EXCLUDED.note,
                    created_by = EXCLUDED.created_by,
                    created_at = EXCLUDED.created_at
                """,
                (
                    p.get("log_id") or perf_doc.id,
                    staff_user_id,
                    p.get("note", ""),
                    safe_text(p.get("created_by")),
                    to_ts(p.get("created_at")),
                ),
            )
            stats.performance_logs += 1


def migrate_attendance(db, cur, stats: MigrationStats) -> None:
    for user_doc in db.collection("attendance").stream():
        user_id = user_doc.id
        records = db.collection("attendance").document(user_id).collection("records").stream()
        for rec_doc in records:
            r = rec_doc.to_dict() or {}
            cur.execute(
                """
                INSERT INTO attendance_logs (
                    record_id, user_id, attendance_date, punch_in, punch_out,
                    status, duration_minutes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    attendance_date = EXCLUDED.attendance_date,
                    punch_in = EXCLUDED.punch_in,
                    punch_out = EXCLUDED.punch_out,
                    status = EXCLUDED.status,
                    duration_minutes = EXCLUDED.duration_minutes,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    rec_doc.id,
                    r.get("user_id") or user_id,
                    to_date(r.get("date")),
                    to_ts(r.get("punch_in")),
                    to_ts(r.get("punch_out")),
                    r.get("status", "out"),
                    to_int(r.get("duration_minutes"), default=0),
                    to_ts(r.get("created_at")),
                    to_ts(r.get("updated_at")),
                ),
            )
            stats.attendance += 1


def migrate_financial_requests(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("financial_requests").stream():
        data = doc.to_dict() or {}
        cur.execute(
            """
            INSERT INTO financial_requests (
                request_id, user_id, type, category, amount, receipt_gcs_path,
                notes, status, admin_notes, reviewed_by, reviewed_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (request_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                type = EXCLUDED.type,
                category = EXCLUDED.category,
                amount = EXCLUDED.amount,
                receipt_gcs_path = EXCLUDED.receipt_gcs_path,
                notes = EXCLUDED.notes,
                status = EXCLUDED.status,
                admin_notes = EXCLUDED.admin_notes,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = EXCLUDED.reviewed_at,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("request_id") or doc.id,
                data.get("user_id", ""),
                data.get("type", "shop_expense"),
                safe_text(data.get("category")),
                to_float(data.get("amount"), default=0.0),
                safe_text(data.get("receipt_gcs_path")),
                safe_text(data.get("notes")),
                data.get("status", "pending"),
                safe_text(data.get("admin_notes")),
                safe_text(data.get("reviewed_by")),
                to_ts(data.get("reviewed_at")),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.financial_requests += 1


def migrate_overtime_records(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("overtime_records").stream():
        data = doc.to_dict() or {}
        cur.execute(
            """
            INSERT INTO overtime_records (
                record_id, user_id, staff_name, full_name, record_date,
                total_worked_minutes, overtime_minutes, hourly_rate, calculated_payout,
                status, reviewed_by, reviewed_at, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (record_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                staff_name = EXCLUDED.staff_name,
                full_name = EXCLUDED.full_name,
                record_date = EXCLUDED.record_date,
                total_worked_minutes = EXCLUDED.total_worked_minutes,
                overtime_minutes = EXCLUDED.overtime_minutes,
                hourly_rate = EXCLUDED.hourly_rate,
                calculated_payout = EXCLUDED.calculated_payout,
                status = EXCLUDED.status,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = EXCLUDED.reviewed_at,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("record_id") or doc.id,
                data.get("user_id", ""),
                safe_text(data.get("staff_name")),
                safe_text(data.get("full_name")),
                to_date(data.get("date")),
                to_int(data.get("total_worked_minutes"), default=0),
                to_int(data.get("overtime_minutes"), default=0),
                to_float(data.get("hourly_rate"), default=0.0),
                to_float(data.get("calculated_payout"), default=0.0),
                data.get("status", "pending"),
                safe_text(data.get("reviewed_by")),
                to_ts(data.get("reviewed_at")),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.overtime_records += 1


def migrate_settlements(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("settlements").stream():
        data = doc.to_dict() or {}
        cur.execute(
            """
            INSERT INTO settlements (
                settlement_id, user_id, full_name, designation, salary_type, settlement_cycle,
                week_start, week_end, weekly_salary, monthly_salary, daily_salary, days_present,
                base_pay, overtime_pay, expenses, advances, net_payable,
                hours_worked, ot_hours, carry_forward_in, amount_settled, carry_forward,
                settlement_status, generated_by, settled_by, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (settlement_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                full_name = EXCLUDED.full_name,
                designation = EXCLUDED.designation,
                salary_type = EXCLUDED.salary_type,
                settlement_cycle = EXCLUDED.settlement_cycle,
                week_start = EXCLUDED.week_start,
                week_end = EXCLUDED.week_end,
                weekly_salary = EXCLUDED.weekly_salary,
                monthly_salary = EXCLUDED.monthly_salary,
                daily_salary = EXCLUDED.daily_salary,
                days_present = EXCLUDED.days_present,
                base_pay = EXCLUDED.base_pay,
                overtime_pay = EXCLUDED.overtime_pay,
                expenses = EXCLUDED.expenses,
                advances = EXCLUDED.advances,
                net_payable = EXCLUDED.net_payable,
                hours_worked = EXCLUDED.hours_worked,
                ot_hours = EXCLUDED.ot_hours,
                carry_forward_in = EXCLUDED.carry_forward_in,
                amount_settled = EXCLUDED.amount_settled,
                carry_forward = EXCLUDED.carry_forward,
                settlement_status = EXCLUDED.settlement_status,
                generated_by = EXCLUDED.generated_by,
                settled_by = EXCLUDED.settled_by,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("settlement_id") or doc.id,
                data.get("user_id", ""),
                safe_text(data.get("full_name")),
                safe_text(data.get("designation")),
                safe_text(data.get("salary_type")) or "weekly",
                safe_text(data.get("settlement_cycle")) or safe_text(data.get("salary_type")) or "weekly",
                to_date(data.get("week_start")),
                to_date(data.get("week_end")),
                to_float(data.get("weekly_salary"), default=0.0) if data.get("weekly_salary") is not None else None,
                to_float(data.get("monthly_salary"), default=0.0) if data.get("monthly_salary") is not None else None,
                to_float(data.get("daily_salary"), default=0.0) if data.get("daily_salary") is not None else None,
                to_int(data.get("days_present"), default=0),
                to_float(data.get("base_pay"), default=0.0),
                to_float(data.get("overtime_pay"), default=0.0),
                to_float(data.get("expenses"), default=0.0),
                to_float(data.get("advances"), default=0.0),
                to_float(data.get("net_payable"), default=0.0),
                to_float(data.get("hours_worked"), default=0.0),
                to_float(data.get("ot_hours"), default=0.0),
                to_float(data.get("carry_forward_in"), default=0.0),
                to_float(data.get("amount_settled"), default=0.0),
                to_float(data.get("carry_forward"), default=0.0),
                safe_text(data.get("settlement_status")) or "pending",
                safe_text(data.get("generated_by")),
                safe_text(data.get("settled_by")),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.settlements += 1


def migrate_leave_requests(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("leave_requests").stream():
        data = doc.to_dict() or {}
        cur.execute(
            """
            INSERT INTO leave_requests (
                request_id, user_id, leave_type, start_date, end_date, half_day_period,
                reason, status, admin_notes, reviewed_by, reviewed_at,
                total_days, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (request_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                leave_type = EXCLUDED.leave_type,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                half_day_period = EXCLUDED.half_day_period,
                reason = EXCLUDED.reason,
                status = EXCLUDED.status,
                admin_notes = EXCLUDED.admin_notes,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = EXCLUDED.reviewed_at,
                total_days = EXCLUDED.total_days,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                data.get("request_id") or doc.id,
                data.get("user_id", ""),
                data.get("leave_type", "full_day"),
                to_date(data.get("start_date")),
                to_date(data.get("end_date")),
                safe_text(data.get("half_day_period")),
                data.get("reason", ""),
                data.get("status", "pending"),
                safe_text(data.get("admin_notes")),
                safe_text(data.get("reviewed_by")),
                to_ts(data.get("reviewed_at")),
                to_float(data.get("total_days"), default=0.0),
                to_ts(data.get("created_at")),
                to_ts(data.get("updated_at")),
            ),
        )
        stats.leave_requests += 1


def migrate_settings(db, cur, stats: MigrationStats) -> None:
    for doc in db.collection("settings").stream():
        data = doc.to_dict() or {}
        config = dict(data)
        updated_by = config.pop("updated_by", None)
        updated_at = config.pop("updated_at", None)
        cur.execute(
            """
            INSERT INTO app_settings (config_type, config, updated_by, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (config_type) DO UPDATE SET
                config = EXCLUDED.config,
                updated_by = EXCLUDED.updated_by,
                updated_at = EXCLUDED.updated_at
            """,
            (
                doc.id,
                Json(config),
                safe_text(updated_by),
                to_ts(updated_at),
            ),
        )
        stats.settings += 1


def run_dry_scan(db) -> MigrationStats:
    stats = MigrationStats()
    stats.admins = sum(1 for _ in db.collection("admins").stream())

    staff_docs = list(db.collection("staff").stream())
    stats.staff = len(staff_docs)
    for staff_doc in staff_docs:
        uid = staff_doc.id
        stats.gallery += sum(1 for _ in db.collection("staff").document(uid).collection("work_gallery").stream())
        stats.performance_logs += sum(1 for _ in db.collection("staff").document(uid).collection("performance_logs").stream())

    for attendance_doc in db.collection("attendance").stream():
        uid = attendance_doc.id
        stats.attendance += sum(1 for _ in db.collection("attendance").document(uid).collection("records").stream())

    stats.financial_requests = sum(1 for _ in db.collection("financial_requests").stream())
    stats.overtime_records = sum(1 for _ in db.collection("overtime_records").stream())
    stats.settlements = sum(1 for _ in db.collection("settlements").stream())
    stats.leave_requests = sum(1 for _ in db.collection("leave_requests").stream())
    stats.settings = sum(1 for _ in db.collection("settings").stream())
    return stats


def main() -> None:
    args = parse_args()
    load_env()

    db = get_firestore()

    if args.dry_run:
        stats = run_dry_scan(db)
        print(json.dumps({"mode": "dry-run", "counts": stats.as_dict()}, indent=2))
        return

    conn = get_conn()
    try:
        if args.apply_schema:
            apply_schema(conn)

        stats = MigrationStats()
        with conn:
            with conn.cursor() as cur:
                migrate_admins(db, cur, stats)
                migrate_staff_and_subcollections(db, cur, stats)
                migrate_attendance(db, cur, stats)
                migrate_financial_requests(db, cur, stats)
                migrate_overtime_records(db, cur, stats)
                migrate_settlements(db, cur, stats)
                migrate_leave_requests(db, cur, stats)
                migrate_settings(db, cur, stats)

        print(json.dumps({"mode": "write", "counts": stats.as_dict()}, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()