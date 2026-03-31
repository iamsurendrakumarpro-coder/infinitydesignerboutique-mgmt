#!/usr/bin/env python3
"""Reset and seed PostgreSQL with deterministic, high-volume end-to-end data."""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import bcrypt
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json


ROOT_DIR = Path(__file__).resolve().parents[1]
IST = timezone(timedelta(hours=5, minutes=30))
SEED_RANDOM = 20260329

DESIGNATIONS = [
    "cutting_master",
    "tailor",
    "embroidery_artist",
    "handwork_expert",
    "designer",
    "helper",
]

DESIGNATION_SKILLS = {
    "cutting_master": ["pattern", "cutting", "measurement"],
    "tailor": ["machine_stitching", "finishing", "fitting"],
    "embroidery_artist": ["zari", "aari", "mirror_work"],
    "handwork_expert": ["beads", "sequins", "hand_finishing"],
    "designer": ["design", "styling", "client_consultation"],
    "helper": ["support", "packing", "floor_assist"],
}

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna", "Ishaan", "Kabir",
    "Rohan", "Karthik", "Rahul", "Aniket", "Nikhil", "Manish", "Deepak", "Vikram", "Suresh", "Rajat",
    "Asha", "Neha", "Kavya", "Pooja", "Meera", "Ira", "Ananya", "Riya", "Diya", "Sneha",
    "Priya", "Naina", "Harini", "Divya", "Shreya", "Nidhi", "Rashmi", "Payal", "Komal", "Ishita",
]

LAST_NAMES = [
    "Sharma", "Verma", "Nair", "Rao", "Kumar", "Patel", "Gupta", "Mehta", "Das", "Singh",
    "Yadav", "Pillai", "Iyer", "Joshi", "Kulkarni", "Mishra", "Bose", "Pandey", "Bhat", "Jain",
]


@dataclass(frozen=True)
class SeedSize:
    staff_count: int
    attendance_days: int
    financial_per_staff: tuple[int, int]
    leave_per_staff: tuple[int, int]
    gallery_ratio: float
    performance_ratio: float


SIZE_PRESETS = {
    "lite": SeedSize(18, 14, (1, 1), (0, 1), 0.20, 0.25),
    "small": SeedSize(24, 21, (1, 2), (0, 1), 0.25, 0.30),
    "medium": SeedSize(80, 35, (1, 3), (0, 2), 0.40, 0.45),
    "large": SeedSize(180, 56, (2, 4), (1, 3), 0.55, 0.60),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset PostgreSQL data and seed deterministic E2E test dataset")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not clear existing data; upsert deterministic seed records",
    )
    parser.add_argument(
        "--size",
        choices=tuple(SIZE_PRESETS.keys()),
        default="lite",
        help="Dataset size profile",
    )
    return parser.parse_args()


def load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default or "")
    if not value:
        raise ValueError(f"Missing environment variable: {name}")
    return value


def get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=_env("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=_env("POSTGRES_DB"),
        user=_env("POSTGRES_USER"),
        password=_env("POSTGRES_PASSWORD"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
        connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "15")),
    )


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def truncate_all_tables(cur) -> int:
    cur.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
    )
    tables = [row[0] for row in cur.fetchall()]
    if not tables:
        return 0

    table_refs = ", ".join(f'public."{name}"' for name in tables)
    cur.execute(f"TRUNCATE TABLE {table_refs} RESTART IDENTITY CASCADE")
    return len(tables)


def seed_admins(cur, now_ts: datetime, pin_hashes: dict[str, str]) -> int:
    rows = [
        (
            "seed-root-admin",
            "Root Admin",
            "9999999999",
            pin_hashes["0000"],
            "admin",
            True,
            False,
            "system",
            now_ts,
            now_ts,
        ),
        (
            "seed-admin-vijay-sharma",
            "Vijay Sharma",
            "9876543210",
            pin_hashes["1234"],
            "admin",
            False,
            False,
            "seed-root-admin",
            now_ts,
            now_ts,
        ),
        (
            "seed-manager-anita-iyer",
            "Anita Iyer",
            "9888888888",
            pin_hashes["2468"],
            "manager",
            False,
            False,
            "seed-root-admin",
            now_ts,
            now_ts,
        ),
        (
            "seed-manager-rohit-nair",
            "Rohit Nair",
            "9777777777",
            pin_hashes["1357"],
            "manager",
            False,
            False,
            "seed-root-admin",
            now_ts,
            now_ts,
        ),
    ]

    cur.executemany(
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
        rows,
    )
    return len(rows)


def build_staff_data(config: SeedSize, now_ts: datetime, rng: random.Random, pin_hashes: dict[str, str]) -> list[dict]:
    staff = []
    start_phone = 9100000000

    for idx in range(1, config.staff_count + 1):
        first = FIRST_NAMES[(idx - 1) % len(FIRST_NAMES)]
        last = LAST_NAMES[((idx - 1) * 3) % len(LAST_NAMES)]
        full_name = f"{first} {last}"
        designation = DESIGNATIONS[(idx - 1) % len(DESIGNATIONS)]
        salary_type = "weekly" if idx % 4 != 0 else "monthly"
        settlement_cycle = salary_type

        if salary_type == "weekly":
            weekly_salary = float(rng.randrange(2200, 7200, 100))
            monthly_salary = None
            daily_salary = round(weekly_salary / 6.0, 2)
        else:
            monthly_salary = float(rng.randrange(18000, 46000, 500))
            weekly_salary = None
            daily_salary = round(monthly_salary / 26.0, 2)

        status_roll = rng.random()
        if status_roll < 0.82:
            status = "active"
        elif status_roll < 0.95:
            status = "inactive"
        else:
            status = "deactivated"

        created_at = now_ts - timedelta(days=rng.randint(5, 420))
        user_id = f"seed-staff-{idx:04d}"

        staff.append(
            {
                "user_id": user_id,
                "full_name": full_name,
                "phone_number": str(start_phone + idx),
                "designation": designation,
                "joining_date": (now_ts.date() - timedelta(days=rng.randint(30, 900))),
                "standard_login_time": "10:00",
                "standard_logout_time": "19:00",
                "emergency_contact": str(9800000000 + idx),
                "salary_type": salary_type,
                "settlement_cycle": settlement_cycle,
                "weekly_salary": weekly_salary,
                "monthly_salary": monthly_salary,
                "daily_salary": daily_salary,
                "skills": DESIGNATION_SKILLS[designation],
                "status": status,
                "pin_hash": pin_hashes["1111"],
                "role": "staff",
                "is_first_login": False,
                "govt_proof": Json({"type": "aadhaar", "last4": f"{1000 + (idx % 9000):04d}"}),
                "created_by": "seed-admin-vijay-sharma",
                "created_at": created_at,
                "updated_at": now_ts,
            }
        )

    return staff


def seed_staff(cur, staff_data: list[dict]) -> int:
    rows = [
        (
            s["user_id"],
            s["full_name"],
            s["phone_number"],
            s["designation"],
            s["joining_date"],
            s["standard_login_time"],
            s["standard_logout_time"],
            s["emergency_contact"],
            s["salary_type"],
            s["settlement_cycle"],
            s["weekly_salary"],
            s["monthly_salary"],
            s["daily_salary"],
            s["skills"],
            s["status"],
            s["pin_hash"],
            s["role"],
            s["is_first_login"],
            s["govt_proof"],
            s["created_by"],
            s["created_at"],
            s["updated_at"],
        )
        for s in staff_data
    ]

    cur.executemany(
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
        rows,
    )
    return len(rows)


def seed_staff_performance_logs(cur, staff_data: list[dict], config: SeedSize, now_ts: datetime, rng: random.Random) -> int:
    rows = []
    notes = [
        "Strong output quality with minimal rework.",
        "Handled rush-order turnaround smoothly.",
        "Maintains consistent stitch precision.",
        "Excellent customer-facing communication.",
        "Good collaboration during peak workload.",
    ]
    for s in staff_data:
        if rng.random() > config.performance_ratio:
            continue
        log_count = 1 if rng.random() < 0.7 else 2
        for n in range(log_count):
            created_at = now_ts - timedelta(days=rng.randint(1, 90))
            rows.append(
                (
                    f"perf-{s['user_id']}-{n + 1}",
                    s["user_id"],
                    rng.choice(notes),
                    "seed-manager-anita-iyer",
                    created_at,
                )
            )

    if not rows:
        return 0

    cur.executemany(
        """
        INSERT INTO staff_performance_logs (log_id, user_id, note, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (log_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            note = EXCLUDED.note,
            created_by = EXCLUDED.created_by,
            created_at = EXCLUDED.created_at
        """,
        rows,
    )
    return len(rows)


def seed_staff_work_gallery(cur, staff_data: list[dict], config: SeedSize, now_ts: datetime, rng: random.Random) -> int:
    rows = []
    for s in staff_data:
        if rng.random() > config.gallery_ratio:
            continue
        image_count = 1 if rng.random() < 0.75 else 2
        for n in range(image_count):
            file_name = f"{s['user_id']}-{n + 1}.jpg"
            rows.append(
                (
                    f"gallery-{s['user_id']}-{n + 1}",
                    s["user_id"],
                    f"https://example.com/gallery/{file_name}",
                    f"gallery/{s['user_id']}/{file_name}",
                    f"Work sample {n + 1}",
                    "seed-manager-rohit-nair",
                    now_ts - timedelta(days=rng.randint(1, 120)),
                )
            )

    if not rows:
        return 0

    cur.executemany(
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
        rows,
    )
    return len(rows)


def seed_attendance(cur, staff_data: list[dict], config: SeedSize, now_ts: datetime, rng: random.Random) -> tuple[int, list[dict]]:
    rows = []
    attendance_index = []
    # Avoid seeding attendance for the current day to prevent confusing "already punched" states.
    # Use yesterday as the most-recent seeded attendance date.
    today = (datetime.now(IST).date() - timedelta(days=1))

    for s in staff_data:
        if s["status"] == "deactivated":
            base_prob = 0.10
        elif s["status"] == "inactive":
            base_prob = 0.45
        else:
            base_prob = 0.88

        for day_offset in range(config.attendance_days):
            day = today - timedelta(days=day_offset)
            if day.weekday() == 6:
                continue
            if rng.random() > base_prob:
                continue

            in_hour = 9 if rng.random() < 0.15 else 10
            in_minute = rng.randint(0, 45)
            punch_in_local = datetime.combine(day, time(in_hour, in_minute), tzinfo=IST)
            duration_minutes = rng.randint(430, 700)
            punch_out_local = punch_in_local + timedelta(minutes=duration_minutes)

            record_id = f"att-{s['user_id']}-{day.strftime('%Y%m%d')}"
            rows.append(
                (
                    record_id,
                    s["user_id"],
                    day,
                    punch_in_local.astimezone(timezone.utc),
                    punch_out_local.astimezone(timezone.utc),
                    "out",
                    duration_minutes,
                    now_ts,
                    now_ts,
                )
            )
            attendance_index.append(
                {
                    "record_id": record_id,
                    "user_id": s["user_id"],
                    "full_name": s["full_name"],
                    "attendance_date": day,
                    "duration_minutes": duration_minutes,
                    "daily_salary": float(s["daily_salary"]),
                }
            )

    if rows:
        cur.executemany(
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
            rows,
        )

    return len(rows), attendance_index


def seed_financial(cur, staff_data: list[dict], config: SeedSize, now_ts: datetime, rng: random.Random) -> int:
    rows = []
    expense_categories = ["fabric", "tools", "transport", "misc", "trims"]
    advance_categories = ["medical", "family", "rent", "education"]

    for s in staff_data:
        request_count = rng.randint(config.financial_per_staff[0], config.financial_per_staff[1])
        for n in range(request_count):
            req_type = "shop_expense" if rng.random() < 0.58 else "personal_advance"
            status_roll = rng.random()
            if status_roll < 0.45:
                status = "pending"
            elif status_roll < 0.82:
                status = "approved"
            else:
                status = "rejected"

            category = rng.choice(expense_categories if req_type == "shop_expense" else advance_categories)
            amount = float(rng.randrange(300, 6500, 50))
            reviewed_by = "seed-admin-vijay-sharma" if status != "pending" else None
            reviewed_at = now_ts - timedelta(days=rng.randint(0, 30)) if status != "pending" else None
            admin_notes = None
            if status == "approved":
                admin_notes = "Approved after review"
            elif status == "rejected":
                admin_notes = "Rejected due to policy limits"

            # Explicit reimbursement workflow seed data for unified payouts page.
            reimbursement_status = "pending"
            reimbursed_by = None
            reimbursed_at = None
            reimbursement_notes = ""

            if req_type != "shop_expense":
                reimbursement_status = "not_applicable"
            elif status != "approved":
                reimbursement_status = "pending"
            elif rng.random() < 0.35:
                reimbursement_status = "paid"
                reimbursed_by = "seed-admin-vijay-sharma"
                paid_at_base = reviewed_at or (now_ts - timedelta(days=rng.randint(1, 20)))
                reimbursed_at = min(now_ts, paid_at_base + timedelta(days=rng.randint(0, 7)))
                reimbursement_notes = "Seeded payout via UPI"

            rows.append(
                (
                    f"fin-{s['user_id']}-{n + 1}",
                    s["user_id"],
                    req_type,
                    category,
                    amount,
                    None,
                    f"Seed request {n + 1} for {category}",
                    status,
                    admin_notes,
                    reviewed_by,
                    reviewed_at,
                    now_ts - timedelta(days=rng.randint(1, 120)),
                    now_ts,
                    reimbursement_status,
                    reimbursed_by,
                    reimbursed_at,
                    reimbursement_notes,
                )
            )

    cur.executemany(
        """
        INSERT INTO financial_requests (
            request_id, user_id, type, category, amount, receipt_gcs_path, notes,
            status, admin_notes, reviewed_by, reviewed_at, created_at, updated_at,
            reimbursement_status, reimbursed_by, reimbursed_at, reimbursement_notes
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
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
            updated_at = EXCLUDED.updated_at,
            reimbursement_status = EXCLUDED.reimbursement_status,
            reimbursed_by = EXCLUDED.reimbursed_by,
            reimbursed_at = EXCLUDED.reimbursed_at,
            reimbursement_notes = EXCLUDED.reimbursement_notes
        """,
        rows,
    )
    return len(rows)


def seed_overtime(cur, attendance_index: list[dict], now_ts: datetime, rng: random.Random) -> int:
    rows = []
    # Use same shift defaults as seed_settings to compute OT so seeded OT matches production logic
    STD_LOGIN = "10:00"
    STD_LOGOUT = "19:00"
    OVERTIME_GRACE = 30

    def _minutes_from_hhmm(s: str) -> int:
        try:
            h, m = map(int, str(s).split(":"))
            return h * 60 + m
        except Exception:
            return 0

    li = _minutes_from_hhmm(STD_LOGIN)
    lo = _minutes_from_hhmm(STD_LOGOUT)
    shift_minutes = (lo - li) % (24 * 60) or 8 * 60

    for entry in attendance_index:
        worked = int(entry.get("duration_minutes", 0))
        # skip short days
        if worked <= 0:
            continue
        # only consider days that exceed the detection threshold
        if worked <= (shift_minutes + OVERTIME_GRACE):
            continue
        # sample probability to avoid OT for every long day
        if rng.random() > 0.35:
            continue

        # Compute overtime as worked - shift - grace (rounded to nearest 5)
        raw_ot = max(0, worked - shift_minutes - OVERTIME_GRACE)
        # Round to nearest 5 minutes for seeded realism
        overtime_minutes = int(round(raw_ot / 5.0) * 5)
        if overtime_minutes <= 0:
            continue

        total_worked = worked
        hourly_rate = round(float(entry["daily_salary"]) / 8.0, 2) if entry.get("daily_salary") else 0.0
        payout = round((hourly_rate / 60.0) * overtime_minutes, 2)

        status_roll = rng.random()
        if status_roll < 0.50:
            status = "pending"
        elif status_roll < 0.83:
            status = "approved"
        else:
            status = "rejected"

        reviewed_by = "seed-admin-vijay-sharma" if status != "pending" else None
        reviewed_at = now_ts - timedelta(days=rng.randint(0, 20)) if status != "pending" else None

        rows.append(
            (
                f"ot-{entry['user_id']}-{entry['attendance_date'].strftime('%Y%m%d')}",
                entry["user_id"],
                entry["full_name"],
                entry["full_name"],
                entry["attendance_date"],
                total_worked,
                overtime_minutes,
                hourly_rate,
                payout,
                status,
                reviewed_by,
                reviewed_at,
                now_ts,
                now_ts,
            )
        )

    if not rows:
        return 0

    cur.executemany(
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
        rows,
    )
    return len(rows)


def seed_settlements(cur, staff_data: list[dict], now_ts: datetime, rng: random.Random) -> int:
    rows = []
    today = datetime.now(IST).date()
    this_monday = today - timedelta(days=today.weekday())

    for s in staff_data:
        carry_in = 0.0

        if s["salary_type"] == "weekly":
            periods = []
            for offset in (4, 3, 2, 1):
                week_start = this_monday - timedelta(days=7 * offset)
                week_end = week_start + timedelta(days=5)
                periods.append((week_start, week_end, "weekly"))
        else:
            periods = []
            base_month = date(today.year, today.month, 1)
            for offset in (3, 2, 1):
                month_seed = base_month - timedelta(days=offset * 31)
                month_start = date(month_seed.year, month_seed.month, 1)
                if month_start.month == 12:
                    next_month = date(month_start.year + 1, 1, 1)
                else:
                    next_month = date(month_start.year, month_start.month + 1, 1)
                month_end = next_month - timedelta(days=1)
                periods.append((month_start, month_end, "monthly"))

        for period_idx, (period_start, period_end, cycle) in enumerate(periods, start=1):
            if cycle == "weekly":
                expected_days = 6
                days_present = rng.randint(4, 6)
                base_pay = round(float(s["weekly_salary"] or 0.0) * (days_present / expected_days), 2)
            else:
                expected_days = 26
                days_present = rng.randint(18, 26)
                base_pay = round(float(s["monthly_salary"] or 0.0) * (days_present / expected_days), 2)

            overtime_pay = round(rng.uniform(0.0, 600.0), 2)
            expenses = round(rng.uniform(0.0, 450.0), 2)
            advances = round(rng.uniform(0.0, 900.0), 2)
            hours_worked = round(days_present * rng.uniform(8.0, 10.5), 2)
            ot_hours = round(rng.uniform(0.0, 8.0), 2)
            net_payable = round(base_pay + overtime_pay + expenses - advances + carry_in, 2)
            if net_payable < 0:
                net_payable = 0.0

            status_roll = rng.random()
            if status_roll < 0.55:
                status = "settled"
                amount_settled = net_payable
                carry_forward = 0.0
                settled_by = "seed-admin-vijay-sharma"
            elif status_roll < 0.85:
                status = "partial"
                amount_settled = round(net_payable * rng.uniform(0.4, 0.85), 2)
                carry_forward = round(net_payable - amount_settled, 2)
                settled_by = "seed-admin-vijay-sharma"
            else:
                status = "pending"
                amount_settled = 0.0
                carry_forward = net_payable
                settled_by = None

            rows.append(
                (
                    f"settle-{s['user_id']}-{period_idx}",
                    s["user_id"],
                    s["full_name"],
                    s["designation"],
                    s["salary_type"],
                    cycle,
                    period_start,
                    period_end,
                    s["weekly_salary"],
                    s["monthly_salary"],
                    s["daily_salary"],
                    days_present,
                    base_pay,
                    overtime_pay,
                    expenses,
                    advances,
                    net_payable,
                    hours_worked,
                    ot_hours,
                    carry_in,
                    amount_settled,
                    carry_forward,
                    status,
                    "seed-admin-vijay-sharma",
                    settled_by,
                    now_ts,
                    now_ts,
                )
            )
            carry_in = carry_forward

    cur.executemany(
        """
        INSERT INTO settlements (
            settlement_id, user_id, full_name, designation, salary_type, settlement_cycle,
            week_start, week_end, weekly_salary, monthly_salary, daily_salary, days_present,
            base_pay, overtime_pay, expenses, advances, net_payable, hours_worked, ot_hours,
            carry_forward_in, amount_settled, carry_forward, settlement_status,
            generated_by, settled_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
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
        rows,
    )
    return len(rows)


def seed_leave_requests(cur, staff_data: list[dict], config: SeedSize, now_ts: datetime, rng: random.Random) -> int:
    rows = []
    leave_types = ["half_day", "full_day", "multiple_days"]

    for s in staff_data:
        leave_count = rng.randint(config.leave_per_staff[0], config.leave_per_staff[1])
        for n in range(leave_count):
            leave_type = rng.choice(leave_types)
            start_date = (datetime.now(IST).date() - timedelta(days=rng.randint(1, 120)))
            if leave_type == "half_day":
                end_date = start_date
                half_day_period = rng.choice(["morning", "afternoon"])
                total_days = 0.5
            elif leave_type == "full_day":
                end_date = start_date
                half_day_period = None
                total_days = 1.0
            else:
                span = rng.randint(2, 5)
                end_date = start_date + timedelta(days=span - 1)
                half_day_period = None
                total_days = float(span)

            status_roll = rng.random()
            if status_roll < 0.50:
                status = "pending"
            elif status_roll < 0.80:
                status = "approved"
            elif status_roll < 0.95:
                status = "rejected"
            else:
                status = "cancelled"

            reviewed_by = "seed-manager-anita-iyer" if status in {"approved", "rejected"} else None
            reviewed_at = now_ts - timedelta(days=rng.randint(0, 20)) if reviewed_by else None
            admin_notes = None
            if status == "approved":
                admin_notes = "Approved"
            elif status == "rejected":
                admin_notes = "Rejected due to staffing constraints"

            rows.append(
                (
                    f"leave-{s['user_id']}-{n + 1}",
                    s["user_id"],
                    leave_type,
                    start_date,
                    end_date,
                    half_day_period,
                    f"Seed leave request {n + 1}",
                    status,
                    admin_notes,
                    reviewed_by,
                    reviewed_at,
                    total_days,
                    now_ts,
                    now_ts,
                )
            )

    cur.executemany(
        """
        INSERT INTO leave_requests (
            request_id, user_id, leave_type, start_date, end_date, half_day_period,
            reason, status, admin_notes, reviewed_by, reviewed_at,
            total_days, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        rows,
    )
    return len(rows)


def seed_settings(cur, now_ts: datetime) -> int:
    rows = [
        (
            "app_config",
            Json(
                {
                    "boutique_name": "Infinity Designer Boutique",
                    "timezone": "Asia/Kolkata",
                    "default_login_time": "10:00",
                    "default_logout_time": "19:00",
                    "standard_hours_per_day": 8,
                    "overtime_grace_minutes": 30,
                    "working_days_per_week": 6,
                    "monthly_working_days": 26,
                }
            ),
            "seed-root-admin",
            now_ts,
        ),
        (
            "designations",
            Json(
                {
                    "list": DESIGNATIONS,
                    "labels": {
                        "cutting_master": "Cutting Master",
                        "tailor": "Tailor",
                        "embroidery_artist": "Embroidery Artist",
                        "handwork_expert": "Handwork Expert",
                        "designer": "Designer",
                        "helper": "Helper",
                    },
                }
            ),
            "seed-root-admin",
            now_ts,
        ),
        (
            "staff_statuses",
            Json({"list": ["active", "inactive", "deactivated"]}),
            "seed-root-admin",
            now_ts,
        ),
        (
            "salary_config",
            Json({"salary_types": ["weekly", "monthly"], "settlement_cycles": ["weekly", "monthly"]}),
            "seed-root-admin",
            now_ts,
        ),
    ]

    cur.executemany(
        """
        INSERT INTO app_settings (config_type, config, updated_by, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (config_type) DO UPDATE SET
            config = EXCLUDED.config,
            updated_by = EXCLUDED.updated_by,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )
    return len(rows)


def main() -> None:
    args = parse_args()
    load_env()

    rng = random.Random(SEED_RANDOM)
    now_ts = datetime.now(timezone.utc)
    config = SIZE_PRESETS[args.size]

    pin_hashes = {
        "0000": hash_pin("0000"),
        "1234": hash_pin("1234"),
        "2468": hash_pin("2468"),
        "1357": hash_pin("1357"),
        "1111": hash_pin("1111"),
    }

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if not args.no_reset:
                    truncated = truncate_all_tables(cur)
                    print(f"Cleared existing data from {truncated} tables.")

                staff_data = build_staff_data(config, now_ts, rng, pin_hashes)

                counts = {
                    "admins": seed_admins(cur, now_ts, pin_hashes),
                    "staff": seed_staff(cur, staff_data),
                    "staff_performance_logs": seed_staff_performance_logs(cur, staff_data, config, now_ts, rng),
                    "staff_work_gallery": seed_staff_work_gallery(cur, staff_data, config, now_ts, rng),
                }

                attendance_count, attendance_index = seed_attendance(cur, staff_data, config, now_ts, rng)
                counts["attendance_logs"] = attendance_count
                counts["financial_requests"] = seed_financial(cur, staff_data, config, now_ts, rng)
                counts["overtime_records"] = seed_overtime(cur, attendance_index, now_ts, rng)
                counts["settlements"] = seed_settlements(cur, staff_data, now_ts, rng)
                counts["leave_requests"] = seed_leave_requests(cur, staff_data, config, now_ts, rng)
                counts["app_settings"] = seed_settings(cur, now_ts)

        print("\nSeed complete.")
        print(f"Dataset profile: {args.size}")
        for key, value in counts.items():
            print(f"  {key}: {value}")

        print("\nLogin test users:")
        print("  Root Admin: 9999999999 / 0000")
        print("  Admin:      9876543210 / 1234")
        print("  Manager:    9888888888 / 2468")
        print("  Manager:    9777777777 / 1357")
        print("  Staff:      9100000001 / 1111")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
