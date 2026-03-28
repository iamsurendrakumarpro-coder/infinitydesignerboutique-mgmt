#!/usr/bin/env python3
"""
seed_data.py - End-to-End Test Data Seeder
Infinity Designer Boutique Management System

Usage:
    python seed_data.py

What it does:
    1. Deletes ALL existing data in every Firestore collection used by the app.
    2. Seeds fresh, realistic data that exercises every feature:
         - Admins    (root + regular)
         - Staff     (4 active + 1 inactive, mixed designations)
         - Attendance (current week Mon-today per active staff, incl. OT shifts)
         - Financial requests (pending / approved / rejected for staff)
         - Overtime records   (auto-derived from long attendance days)
         - Settlements        (previous week, two staff members)
         - Performance logs   (per staff)
         - Work gallery       (per staff)

Seeded credentials   phone number    -> PIN  (role):
    Owner (root):    9999999999      -> 0000  (admin, is_root=True)
    Vijay Sharma:    9876543210      -> 1234  (admin)
    Raju Mehta:      9123456789      -> 5678  (staff - tailor,            weekly salary)
    Sunil Rao:       9234567890      -> 4321  (staff - embroidery_artist, weekly salary)
    Arjun Das:       9345678901      -> 9999  (staff - cutting_master,    weekly salary)
    Mohan Kumar:     9456789012      -> 1111  (staff - handwork_expert,   weekly salary)
    Kiran Nair:      9678901234      -> 2222  (staff - designer,          monthly salary)
    Deepak Kumar:    9567890123      -> 0000  (staff - helper, STATUS: inactive)

Staff schema additions (applicable to all staff going forward):
    salary_type      : "weekly" | "monthly"
    settlement_cycle : "weekly" | "monthly"  (admin-configurable per staff member)
    monthly_salary   : present only when salary_type == "monthly"

Attendance pattern for the current working week (Mon-today):
    Raju   : Mon-Tue standard, Wed OVERTIME (+2 h), Thu-Fri standard, Sat in-progress
    Sunil  : Mon standard, Tue OVERTIME (+1.5 h), Wed standard, Thu short, Fri ABSENT, Sat in-progress
    Arjun  : Mon-Wed standard, Thu half-day, Fri OVERTIME (+1 h), Sat in-progress
    Mohan  : Mon-Tue standard, Wed OVERTIME (+2.5 h), Thu-Fri standard, Sat in-progress
    Kiran  : Mon standard, Tue OVERTIME (+3 h), Wed-Fri standard, Sat in-progress
    Deepak : no attendance (account inactive)
"""

from __future__ import annotations

import os
import sys
import bcrypt
from datetime import date, datetime, timedelta, timezone

# -- Load .env before Firebase imports ----------------------------------------
from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore


# =============================================================================
#  Firebase initialisation
# =============================================================================

_CREDS_PATH  = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
_PROJECT_ID  = os.getenv("FIREBASE_PROJECT_ID")

if not os.path.exists(_CREDS_PATH):
    print(f"\n[ERROR] Firebase credentials not found: {_CREDS_PATH}")
    print("  Ensure FIREBASE_CREDENTIALS_PATH is set correctly in .env")
    sys.exit(1)

try:
    _app_opts = {"projectId": _PROJECT_ID} if _PROJECT_ID else {}
    firebase_admin.initialize_app(credentials.Certificate(_CREDS_PATH), _app_opts)
    db  = firestore.client()
    TS  = firestore.SERVER_TIMESTAMP   # sentinel: replaced by server clock on write
    print(f"[OK] Connected to Firestore project: {_PROJECT_ID or '(from credentials file)'}")
except Exception as exc:
    print(f"\n[ERROR] Firebase initialisation failed: {exc}")
    sys.exit(1)


# =============================================================================
#  Deterministic seed document IDs
#  (human-readable in the Firebase console; no random UUIDs)
# =============================================================================

ROOT_ADMIN_ID = "seed-root-admin"
ADMIN_ID      = "seed-admin-vijay-sharma"

RAJU_ID   = "seed-staff-raju-mehta"
SUNITA_ID = "seed-staff-sunil-rao"
ARJUN_ID  = "seed-staff-arjun-das"
MEENA_ID  = "seed-staff-mohan-kumar"
KIRAN_ID  = "seed-staff-kiran-nair"
DEEPAK_ID = "seed-staff-deepak-kumar"

ACTIVE_STAFF = [RAJU_ID, SUNITA_ID, ARJUN_ID, MEENA_ID, KIRAN_ID]


# =============================================================================
#  Helper utilities
# =============================================================================

def _hash_pin(pin: str) -> str:
    """Return a bcrypt hash of a 4-digit PIN (12 rounds, matching auth_service.py)."""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _ist_to_utc(d: date, hour: int, minute: int) -> datetime:
    """
    Build a UTC-aware datetime from an IST date + HH:MM.
    IST = UTC + 5:30 -> subtract 5 h 30 m to get UTC.
    """
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_dt = datetime(d.year, d.month, d.day, hour, minute, 0, tzinfo=ist_tz)
    return ist_dt.astimezone(timezone.utc)


def _doc_id(d: date) -> str:
    """Attendance record document ID: YYYYMMDD (no dashes)."""
    return d.strftime("%Y%m%d")


def _week_dates() -> dict[str, date]:
    """
    Return named IST dates for the current and previous working weeks.
    Working week: Monday (day 0) through Saturday (day 5).
    """
    ist_tz    = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(ist_tz).date()
    # weekday() returns 0=Mon ... 5=Sat, 6=Sun
    curr_mon  = today_ist - timedelta(days=today_ist.weekday())
    return {
        "today":    today_ist,
        "curr_mon": curr_mon,
        "curr_tue": curr_mon + timedelta(1),
        "curr_wed": curr_mon + timedelta(2),
        "curr_thu": curr_mon + timedelta(3),
        "curr_fri": curr_mon + timedelta(4),
        "curr_sat": curr_mon + timedelta(5),
        "prev_mon": curr_mon - timedelta(7),
        "prev_tue": curr_mon - timedelta(6),
        "prev_wed": curr_mon - timedelta(5),
        "prev_thu": curr_mon - timedelta(4),
        "prev_fri": curr_mon - timedelta(3),
        "prev_sat": curr_mon - timedelta(2),
    }


# =============================================================================
#  Deletion
# =============================================================================

_TOP_LEVEL_COLLECTIONS = [
    "admins",
    "staff",              # sub-collections: work_gallery, performance_logs
    "attendance",         # sub-collections: records
    "financial_requests",
    "overtime_records",
    "settlements",
]


def _delete_collection(col_ref, batch: int = 200) -> int:
    """
    Recursively delete all documents (and their sub-collections) in col_ref.
    Returns the total count of deleted documents.
    """
    deleted = 0
    docs = list(col_ref.limit(batch).stream())
    for doc in docs:
        for sub in doc.reference.collections():
            deleted += _delete_collection(sub, batch)
        doc.reference.delete()
        deleted += 1
    if len(docs) == batch:                          # might be more pages
        deleted += _delete_collection(col_ref, batch)
    return deleted


def delete_all() -> None:
    """Wipe every document in all app-relevant Firestore collections."""
    print("\n--- Deleting existing data ---")
    total = 0
    for col_name in _TOP_LEVEL_COLLECTIONS:
        n = _delete_collection(db.collection(col_name))
        if n:
            print(f"  Deleted {n:4d} doc(s) from '{col_name}'")
        total += n
    print(f"  Total deleted: {total} document(s)")


# =============================================================================
#  Seed: Admins
# =============================================================================

def seed_admins() -> None:
    print("\n--- Seeding admins ---")

    # Pre-compute hashes (bcrypt is intentionally slow; do it once each)
    root_hash  = _hash_pin("0000")
    vijay_hash = _hash_pin("1234")

    admins = [
        {
            "user_id":        ROOT_ADMIN_ID,
            "full_name":      "Owner",
            "phone_number":   "9999999999",
            "pin_hash":       root_hash,
            "role":           "admin",
            "is_root":        True,
            "is_first_login": False,
            "created_at":     TS,
            "updated_at":     TS,
            "created_by":     "system",
        },
        {
            "user_id":        ADMIN_ID,
            "full_name":      "Vijay Sharma",
            "phone_number":   "9876543210",
            "pin_hash":       vijay_hash,
            "role":           "admin",
            "is_root":        False,
            "is_first_login": False,
            "created_at":     TS,
            "updated_at":     TS,
            "created_by":     ROOT_ADMIN_ID,
        },
    ]

    for doc in admins:
        db.collection("admins").document(doc["user_id"]).set(doc)
        tag = " [ROOT]" if doc["is_root"] else ""
        print(f"  {doc['full_name']}{tag}  |  {doc['phone_number']}  |  PIN: {'0000' if doc['is_root'] else '1234'}")


# =============================================================================
#  Seed: Staff
# =============================================================================

def seed_staff() -> None:
    """
    Seed 5 staff members across different designations and salary bands.

    Salary bands (weekly -> daily = weekly / 6):
        Raju   : INR  3000 / wk  ->  500.00 / day  (tailor)
        Sunil  : INR  4200 / wk  ->  700.00 / day  (embroidery_artist) - senior
        Arjun  : INR  3600 / wk  ->  600.00 / day  (cutting_master)
        Mohan  : INR  2400 / wk  ->  400.00 / day  (handwork_expert)
        Deepak : INR  1800 / wk  ->  300.00 / day  (helper, inactive)

    Monthly salary (daily = monthly / 26 working days):
        Kiran  : INR 18000 / mo  ->  692.31 / day  (designer, settlement_cycle=monthly)
    """
    print("\n--- Seeding staff ---")

    staff_docs = [
        {
            "user_id":              RAJU_ID,
            "full_name":            "Raju Mehta",
            "phone_number":         "9123456789",
            "designation":          "tailor",
            "joining_date":         "2025-01-15",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "9988776655",
            "weekly_salary":        3000.0,
            "daily_salary":         500.0,       # round(3000 / 6, 2)
            "salary_type":          "weekly",
            "settlement_cycle":     "weekly",
            "skills":               ["machine_stitching", "hand_finishing", "button_work"],
            "status":               "active",
            "pin_hash":             _hash_pin("5678"),
            "role":                 "staff",
            "is_first_login":       False,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
        {
            "user_id":              SUNITA_ID,
            "full_name":            "Sunil Rao",
            "phone_number":         "9234567890",
            "designation":          "embroidery_artist",
            "joining_date":         "2024-06-01",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "",
            "weekly_salary":        4200.0,
            "daily_salary":         700.0,       # round(4200 / 6, 2)
            "salary_type":          "weekly",
            "settlement_cycle":     "weekly",
            "skills":               ["zari_work", "mirror_work", "sequence_work", "aari_embroidery"],
            "status":               "active",
            "pin_hash":             _hash_pin("4321"),
            "role":                 "staff",
            "is_first_login":       False,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
        {
            "user_id":              ARJUN_ID,
            "full_name":            "Arjun Das",
            "phone_number":         "9345678901",
            "designation":          "cutting_master",
            "joining_date":         "2025-03-10",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "9977665544",
            "weekly_salary":        3600.0,
            "daily_salary":         600.0,       # round(3600 / 6, 2)
            "salary_type":          "weekly",
            "settlement_cycle":     "weekly",
            "skills":               ["pattern_cutting", "fabric_marking", "grading"],
            "status":               "active",
            "pin_hash":             _hash_pin("9999"),
            "role":                 "staff",
            "is_first_login":       False,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
        {
            "user_id":              MEENA_ID,
            "full_name":            "Mohan Kumar",
            "phone_number":         "9456789012",
            "designation":          "handwork_expert",
            "joining_date":         "2024-09-01",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "",
            "weekly_salary":        2400.0,
            "daily_salary":         400.0,       # round(2400 / 6, 2)
            "salary_type":          "weekly",
            "settlement_cycle":     "weekly",
            "skills":               ["hand_stitching", "applique", "patchwork", "beadwork"],
            "status":               "active",
            "pin_hash":             _hash_pin("1111"),
            "role":                 "staff",
            "is_first_login":       False,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
        {
            # Designer - customer-facing role; monthly salary, settlement_cycle set by admin
            # daily_salary = round(monthly_salary / 26, 2)  [26 standard working days/month]
            # OT hourly_rate = monthly_salary / 26 / 8
            "user_id":              KIRAN_ID,
            "full_name":            "Kiran Nair",
            "phone_number":         "9678901234",
            "designation":          "designer",
            "joining_date":         "2025-11-01",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "9988001122",
            "monthly_salary":       18000.0,
            "daily_salary":         692.31,      # round(18000 / 26, 2)
            "salary_type":          "monthly",
            "settlement_cycle":     "monthly",   # admin-configurable; monthly for designers
            "skills":               ["pattern_design", "customer_consultation", "fashion_sketching"],
            "status":               "active",
            "pin_hash":             _hash_pin("2222"),
            "role":                 "staff",
            "is_first_login":       False,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
        {
            # Inactive account - cannot log in; shown in staff directory with inactive badge
            "user_id":              DEEPAK_ID,
            "full_name":            "Deepak Kumar",
            "phone_number":         "9567890123",
            "designation":          "helper",
            "joining_date":         "2026-01-10",
            "standard_login_time":  "10:00",
            "standard_logout_time": "19:00",
            "emergency_contact":    "",
            "weekly_salary":        1800.0,
            "daily_salary":         300.0,       # round(1800 / 6, 2)
            "salary_type":          "weekly",
            "settlement_cycle":     "weekly",
            "skills":               [],
            "status":               "inactive",
            "pin_hash":             _hash_pin("0000"),
            "role":                 "staff",
            "is_first_login":       True,
            "created_at":           TS,
            "updated_at":           TS,
            "created_by":           ADMIN_ID,
        },
    ]

    for doc in staff_docs:
        db.collection("staff").document(doc["user_id"]).set(doc)
        flag = f" [{doc['status'].upper()}]" if doc["status"] != "active" else ""
        print(f"  {doc['full_name']:<18}  {doc['designation']:<20}  INR {doc['weekly_salary']:>5}/wk{flag}")


# =============================================================================
#  Seed: Attendance
# =============================================================================

def seed_attendance(days: dict[str, date]) -> None:
    """
    Seed attendance records for the current working week (Mon-today).

    Shift timing reference (IST -> UTC, IST = UTC+5:30):
        10:00 IST = 04:30 UTC  (standard punch-in)
        18:00 IST = 12:30 UTC  (short shift out)
        19:00 IST = 13:30 UTC  (standard punch-out, 540 min = 9 h)
        20:00 IST = 14:30 UTC  (mild OT out, 600 min)
        20:30 IST = 15:00 UTC  (OT out, 630 min)
        21:00 IST = 15:30 UTC  (heavy OT out, 660 min)
        21:30 IST = 16:00 UTC  (heavy OT out, 690 min)

    OT threshold (config.py): duration_minutes > 540  (8h standard + 60 min grace)
    OT minutes = total_worked - 480  (standard 8h * 60 min)

    OT produced today:
        Raju   Wed  660 min  OT =  180 min  payout =  62.50 * 3.0 = 187.50  INR
        Sunil  Tue  630 min  OT =  150 min  payout =  87.50 * 2.5 = 218.75  INR
        Arjun  Fri  600 min  OT =  120 min  payout =  75.00 * 2.0 = 150.00  INR
        Mohan  Wed  690 min  OT =  210 min  payout =  50.00 * 3.5 = 175.00  INR
        Kiran  Tue  660 min  OT =  180 min  payout =  86.54 * 3.0 = 259.62  INR
                             hourly_rate = 18000 / 26 / 8 = 86.54
    """
    print("\n--- Seeding attendance ---")
    total = 0

    def set_rec(uid: str, d: date,
                in_h: int, in_m: int,
                out_h: int | None, out_m: int | None) -> None:
        """Write one attendance record to attendance/{uid}/records/{YYYYMMDD}."""
        nonlocal total
        if d > days["today"]:          # never write future records
            return

        ref = (db.collection("attendance")
                 .document(uid)
                 .collection("records")
                 .document(_doc_id(d)))

        pi = _ist_to_utc(d, in_h, in_m)

        if out_h is not None:
            po       = _ist_to_utc(d, out_h, out_m)
            duration = int((po - pi).total_seconds() // 60)
            rec = {
                "user_id":          uid,
                "date":             d.isoformat(),
                "punch_in":         pi,
                "punch_out":        po,
                "status":           "out",
                "duration_minutes": duration,
                "created_at":       TS,
                "updated_at":       TS,
            }
        else:
            # Today's in-progress record
            rec = {
                "user_id":          uid,
                "date":             d.isoformat(),
                "punch_in":         pi,
                "punch_out":        None,
                "status":           "in",
                "duration_minutes": 0,
                "created_at":       TS,
                "updated_at":       TS,
            }

        ref.set(rec)
        total += 1

    # -- Raju Mehta (tailor, INR 3000/wk, hourly_rate = 62.50) ---------------
    # Mon, Tue, Thu, Fri: standard 10:00-19:00 (540 min)
    for d in [days["curr_mon"], days["curr_tue"], days["curr_thu"], days["curr_fri"]]:
        set_rec(RAJU_ID, d, 10, 0, 19, 0)
    # Wed: overtime 10:00-21:00 (660 min, OT = 180 min, payout = INR 187.50)
    set_rec(RAJU_ID, days["curr_wed"], 10, 0, 21, 0)
    # Sat: punched in (still working)
    set_rec(RAJU_ID, days["curr_sat"], 10, 5, None, None)

    # -- Sunil Rao (embroidery_artist, INR 4200/wk, hourly_rate = 87.50) -----
    # Mon: standard
    set_rec(SUNITA_ID, days["curr_mon"], 10, 0, 19, 0)
    # Tue: overtime 10:00-20:30 (630 min, OT = 150 min, payout = INR 218.75)
    set_rec(SUNITA_ID, days["curr_tue"], 10, 0, 20, 30)
    # Wed: standard
    set_rec(SUNITA_ID, days["curr_wed"], 10, 0, 19, 0)
    # Thu: short shift 10:00-18:00 (480 min, below OT threshold - no OT)
    set_rec(SUNITA_ID, days["curr_thu"], 10, 0, 18, 0)
    # Fri: ABSENT (no record created - tests absent-staff display)
    # Sat: punched in (still working)
    set_rec(SUNITA_ID, days["curr_sat"], 10, 10, None, None)

    # -- Arjun Das (cutting_master, INR 3600/wk, hourly_rate = 75.00) --------
    # Mon, Tue, Wed: standard
    for d in [days["curr_mon"], days["curr_tue"], days["curr_wed"]]:
        set_rec(ARJUN_ID, d, 10, 0, 19, 0)
    # Thu: half-day 10:30-16:30 (360 min, no OT)
    set_rec(ARJUN_ID, days["curr_thu"], 10, 30, 16, 30)
    # Fri: overtime 10:00-20:00 (600 min, OT = 120 min, payout = INR 150.00)
    set_rec(ARJUN_ID, days["curr_fri"], 10, 0, 20, 0)
    # Sat: punched in (still working)
    set_rec(ARJUN_ID, days["curr_sat"], 10, 0, None, None)

    # -- Mohan Kumar (handwork_expert, INR 2400/wk, hourly_rate = 50.00) -----
    # Mon, Tue: standard
    for d in [days["curr_mon"], days["curr_tue"]]:
        set_rec(MEENA_ID, d, 10, 0, 19, 0)
    # Wed: overtime 10:00-21:30 (690 min, OT = 210 min, payout = INR 175.00)
    set_rec(MEENA_ID, days["curr_wed"], 10, 0, 21, 30)
    # Thu, Fri: standard
    for d in [days["curr_thu"], days["curr_fri"]]:
        set_rec(MEENA_ID, d, 10, 0, 19, 0)
    # Sat: punched in (still working)
    set_rec(MEENA_ID, days["curr_sat"], 10, 15, None, None)

    # -- Kiran Nair (designer, INR 18000/mo, hourly_rate = 86.54) -------------
    # Mon: standard
    set_rec(KIRAN_ID, days["curr_mon"], 10, 0, 19, 0)
    # Tue: overtime 10:00-21:00 (660 min, OT = 180 min, payout = INR 259.62)
    set_rec(KIRAN_ID, days["curr_tue"], 10, 0, 21, 0)
    # Wed, Thu, Fri: standard
    for d in [days["curr_wed"], days["curr_thu"], days["curr_fri"]]:
        set_rec(KIRAN_ID, d, 10, 0, 19, 0)
    # Sat: punched in (still working)
    set_rec(KIRAN_ID, days["curr_sat"], 10, 0, None, None)

    # Deepak is inactive - no attendance records

    print(f"  Created {total} attendance record(s) for {len(ACTIVE_STAFF)} active staff")


# =============================================================================
#  Seed: Financial Requests
# =============================================================================

def seed_financial_requests(days: dict[str, date]) -> None:
    """
    Seed financial requests covering all statuses (pending / approved / rejected)
    and both types (shop_expense / personal_advance).

    Validation rules enforced:
        personal_advance amount <= staff.weekly_salary
        shop_expense requires a category
    """
    print("\n--- Seeding financial requests ---")

    requests = [
        # -- Raju: pending shop expense (fabric purchase this week)
        {
            "request_id":       "seed-fr-raju-expense-001",
            "user_id":          RAJU_ID,
            "type":             "shop_expense",
            "category":         "fabric",
            "amount":           2000.0,
            "receipt_gcs_path": "",
            "notes":            "Purchased 6 metres of pure silk fabric for upcoming bridal order",
            "status":           "pending",
            "admin_notes":      "",
            "reviewed_by":      None,
            "reviewed_at":      None,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Raju: approved personal advance (medical emergency)
        {
            "request_id":       "seed-fr-raju-advance-001",
            "user_id":          RAJU_ID,
            "type":             "personal_advance",
            "category":         "",
            "amount":           500.0,
            "receipt_gcs_path": "",
            "notes":            "Medical emergency expense - doctor visit",
            "status":           "approved",
            "admin_notes":      "Approved. Will be deducted from next settlement.",
            "reviewed_by":      ADMIN_ID,
            "reviewed_at":      TS,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Raju: rejected personal advance (amount too large, near weekly limit)
        {
            "request_id":       "seed-fr-raju-advance-002",
            "user_id":          RAJU_ID,
            "type":             "personal_advance",
            "category":         "",
            "amount":           2800.0,
            "receipt_gcs_path": "",
            "notes":            "Home repair advance",
            "status":           "rejected",
            "admin_notes":      "Amount too high for this week. Please split into two requests.",
            "reviewed_by":      ADMIN_ID,
            "reviewed_at":      TS,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Sunil: pending shop expense (raw material)
        {
            "request_id":       "seed-fr-sunil-expense-001",
            "user_id":          SUNITA_ID,
            "type":             "shop_expense",
            "category":         "thread",
            "amount":           800.0,
            "receipt_gcs_path": "",
            "notes":            "Zari thread and silk thread for wedding dupatta collection",
            "status":           "pending",
            "admin_notes":      "",
            "reviewed_by":      None,
            "reviewed_at":      None,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Sunil: approved shop expense (mirror work beads - prior week)
        {
            "request_id":       "seed-fr-sunil-expense-002",
            "user_id":          SUNITA_ID,
            "type":             "shop_expense",
            "category":         "embellishments",
            "amount":           1200.0,
            "receipt_gcs_path": "",
            "notes":            "Mirror work beads, sequence rolls for Sharma family order",
            "status":           "approved",
            "admin_notes":      "Receipt verified. Approved for reimbursement.",
            "reviewed_by":      ADMIN_ID,
            "reviewed_at":      TS,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Arjun: rejected personal advance
        {
            "request_id":       "seed-fr-arjun-advance-001",
            "user_id":          ARJUN_ID,
            "type":             "personal_advance",
            "category":         "",
            "amount":           1500.0,
            "receipt_gcs_path": "",
            "notes":            "Festival advance",
            "status":           "rejected",
            "admin_notes":      "Advance already taken this month. Eligible next month.",
            "reviewed_by":      ROOT_ADMIN_ID,
            "reviewed_at":      TS,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Mohan: pending shop expense (hand-stitching material)
        {
            "request_id":       "seed-fr-mohan-expense-001",
            "user_id":          MEENA_ID,
            "type":             "shop_expense",
            "category":         "materials",
            "amount":           600.0,
            "receipt_gcs_path": "",
            "notes":            "Embroidery thread, needles, and backing fabric",
            "status":           "pending",
            "admin_notes":      "",
            "reviewed_by":      None,
            "reviewed_at":      None,
            "created_at":       TS,
            "updated_at":       TS,
        },
        # -- Kiran: pending shop expense (design reference materials)
        {
            "request_id":       "seed-fr-kiran-expense-001",
            "user_id":          KIRAN_ID,
            "type":             "shop_expense",
            "category":         "materials",
            "amount":           1500.0,
            "receipt_gcs_path": "",
            "notes":            "Fashion design books and fabric swatch catalogue for upcoming season lookbook",
            "status":           "pending",
            "admin_notes":      "",
            "reviewed_by":      None,
            "reviewed_at":      None,
            "created_at":       TS,
            "updated_at":       TS,
        },
    ]

    for doc in requests:
        db.collection("financial_requests").document(doc["request_id"]).set(doc)

    # Print summary grouped by staff
    _fr_summary = {}
    for doc in requests:
        uid = doc["user_id"]
        _fr_summary.setdefault(uid, []).append(
            f"{doc['type'][:6]} INR {doc['amount']:.0f} [{doc['status']}]"
        )
    names = {RAJU_ID: "Raju", SUNITA_ID: "Sunil", ARJUN_ID: "Arjun", MEENA_ID: "Mohan", KIRAN_ID: "Kiran"}
    for uid, items in _fr_summary.items():
        print(f"  {names.get(uid, uid)}: {', '.join(items)}")


# =============================================================================
#  Seed: Overtime Records
# =============================================================================

def seed_overtime_records(days: dict[str, date]) -> None:
    """
    Seed overtime records derived from OT attendance shifts.

    Formula (overtime_service.py):
        hourly_rate       = weekly_salary / 6 / 8
        overtime_minutes  = total_worked_minutes - (8 * 60)   [subtract standard 8h]
        calculated_payout = round(hourly_rate * (overtime_minutes / 60), 2)

    OT threshold (attendance_service.py):
        Only created when duration_minutes > 540 (8h + 60 min grace period)

    Records seeded:
        Raju   Wed  660 min  OT 180 min  hourly 62.50  payout INR 187.50  [pending]
        Sunil  Tue  630 min  OT 150 min  hourly 87.50  payout INR 218.75  [approved]
        Arjun  Fri  600 min  OT 120 min  hourly 75.00  payout INR 150.00  [pending]
        Mohan  Wed  690 min  OT 210 min  hourly 50.00  payout INR 175.00  [approved]
        Kiran  Tue  660 min  OT 180 min  hourly 86.54  payout INR 259.62  [pending]
                             (hourly_rate = 18000 / 26 / 8 for monthly-salary staff)
    """
    print("\n--- Seeding overtime records ---")

    records = [
        {
            "record_id":            "seed-ot-raju-wed",
            "user_id":              RAJU_ID,
            "date":                 days["curr_wed"].isoformat(),
            "total_worked_minutes": 660,
            "overtime_minutes":     180,      # 660 - 480 (standard 8h)
            "hourly_rate":          62.5,     # 3000 / 6 / 8
            "calculated_payout":    187.5,    # 62.5 * (180 / 60)
            "status":               "pending",
            "reviewed_by":          None,
            "reviewed_at":          None,
            "created_at":           TS,
            "updated_at":           TS,
        },
        {
            "record_id":            "seed-ot-sunil-tue",
            "user_id":              SUNITA_ID,
            "date":                 days["curr_tue"].isoformat(),
            "total_worked_minutes": 630,
            "overtime_minutes":     150,      # 630 - 480
            "hourly_rate":          87.5,     # 4200 / 6 / 8
            "calculated_payout":    218.75,   # 87.5 * (150 / 60)
            "status":               "approved",
            "reviewed_by":          ADMIN_ID,
            "reviewed_at":          TS,
            "created_at":           TS,
            "updated_at":           TS,
        },
        {
            "record_id":            "seed-ot-arjun-fri",
            "user_id":              ARJUN_ID,
            "date":                 days["curr_fri"].isoformat(),
            "total_worked_minutes": 600,
            "overtime_minutes":     120,      # 600 - 480
            "hourly_rate":          75.0,     # 3600 / 6 / 8
            "calculated_payout":    150.0,    # 75.0 * (120 / 60)
            "status":               "pending",
            "reviewed_by":          None,
            "reviewed_at":          None,
            "created_at":           TS,
            "updated_at":           TS,
        },
        {
            "record_id":            "seed-ot-mohan-wed",
            "user_id":              MEENA_ID,
            "date":                 days["curr_wed"].isoformat(),
            "total_worked_minutes": 690,
            "overtime_minutes":     210,      # 690 - 480
            "hourly_rate":          50.0,     # 2400 / 6 / 8
            "calculated_payout":    175.0,    # 50.0 * (210 / 60)
            "status":               "approved",
            "reviewed_by":          ADMIN_ID,
            "reviewed_at":          TS,
            "created_at":           TS,
            "updated_at":           TS,
        },
        {
            "record_id":            "seed-ot-kiran-tue",
            "user_id":              KIRAN_ID,
            "date":                 days["curr_tue"].isoformat(),
            "total_worked_minutes": 660,
            "overtime_minutes":     180,      # 660 - 480
            "hourly_rate":          86.54,    # round(18000 / 26 / 8, 2)
            "calculated_payout":    259.62,   # 86.54 * (180 / 60)
            "status":               "pending",
            "reviewed_by":          None,
            "reviewed_at":          None,
            "created_at":           TS,
            "updated_at":           TS,
        },
    ]

    for doc in records:
        db.collection("overtime_records").document(doc["record_id"]).set(doc)
        print(
            f"  {doc['date']}  {doc['user_id'].split('-')[-1]:<12}  "
            f"OT {doc['overtime_minutes']} min  "
            f"INR {doc['calculated_payout']:.2f}  [{doc['status']}]"
        )


# =============================================================================
#  Seed: Settlements (previous week)
# =============================================================================

def seed_settlements(days: dict[str, date]) -> None:
    """
    Seed two completed weekly settlements from the previous working week.

    Only staff with settlement_cycle == "weekly" receive weekly settlements.
    Kiran Nair (designer, settlement_cycle="monthly") is excluded here;
    the admin generates his settlement manually at month-end.

    Settlement formula (settlement_service.py):
        net_payable = base_pay + overtime_pay + expenses - advances

    base_pay is proportional to hours worked vs standard 8h per day:
        base_pay = sum over attended days of: daily_salary * (duration_min / 480)

    Previous week scenario:
        Raju   : 5 days x 540 min, no OT, approved advance INR 500
                 base_pay = 5 * 500 * (540/480) = 2812.50
                 net = 2812.50 + 0 + 0 - 500 = 2312.50

        Sunil  : 4 days x 540 min + 1 day OT 630 min, approved expense INR 1200
                 base_pay = 4 * 700 * (540/480) + 700 * (630/480) = 4068.75
                           (= 3150.00 + 918.75)
                 ot_pay   = 87.5 * 2.5 = 218.75
                 net = 4068.75 + 218.75 + 1200 - 0 = 5487.50
    """
    print("\n--- Seeding settlements ---")

    week_start = days["prev_mon"].isoformat()
    week_end   = days["prev_sat"].isoformat()

    settlements = [
        {
            "settlement_id": "seed-settle-raju-prev-week",
            "user_id":       RAJU_ID,
            "full_name":     "Raju Mehta",
            "designation":   "tailor",
            "week_start":    week_start,
            "week_end":      week_end,
            "weekly_salary": 3000.0,
            "daily_salary":  500.0,
            "days_present":  5,
            "base_pay":      2812.5,    # 5 * 500 * (540 / 480)
            "overtime_pay":  0.0,
            "expenses":      0.0,
            "advances":      500.0,     # personal advance approved that week
            "net_payable":   2312.5,    # 2812.5 + 0 + 0 - 500
            "hours_worked":  45.0,      # 5 * 9h
            "ot_hours":      0.0,
            "generated_by":  ADMIN_ID,
            "created_at":    TS,
            "updated_at":    TS,
        },
        {
            "settlement_id": "seed-settle-sunil-prev-week",
            "user_id":       SUNITA_ID,
            "full_name":     "Sunil Rao",
            "designation":   "embroidery_artist",
            "week_start":    week_start,
            "week_end":      week_end,
            "weekly_salary": 4200.0,
            "daily_salary":  700.0,
            "days_present":  5,
            "base_pay":      4068.75,   # 4 * 700 * (540/480) + 700 * (630/480)
            "overtime_pay":  218.75,    # 87.5/h * 2.5h (150 min OT)
            "expenses":      1200.0,    # approved mirror beads expense
            "advances":      0.0,
            "net_payable":   5487.5,    # 4068.75 + 218.75 + 1200 - 0
            "hours_worked":  46.5,      # 4*9 + 10.5
            "ot_hours":      2.5,       # 150 min / 60
            "generated_by":  ADMIN_ID,
            "created_at":    TS,
            "updated_at":    TS,
        },
    ]

    for doc in settlements:
        db.collection("settlements").document(doc["settlement_id"]).set(doc)
        print(
            f"  {doc['full_name']:<18}  "
            f"{doc['week_start']} to {doc['week_end']}  "
            f"net INR {doc['net_payable']:.2f}"
        )


# =============================================================================
#  Seed: Performance Logs (sub-collection of staff)
# =============================================================================

def seed_performance_logs() -> None:
    """
    Seed performance log entries for each active staff member.
    Path: staff/{user_id}/performance_logs/{log_id}
    """
    print("\n--- Seeding performance logs ---")
    total = 0

    logs = [
        (RAJU_ID, "seed-perf-raju-01",
         "Outstanding finishing work on the Kapoor bridal lehenga. "
         "Completed 2 days ahead of schedule with zero rework."),
        (RAJU_ID, "seed-perf-raju-02",
         "Positive client feedback from the Sharma family for the sherwani set. "
         "Very clean button-hole work and precise lining."),
        (SUNITA_ID, "seed-perf-sunil-01",
         "Exceptional zari embroidery on the Mehta wedding dupatta collection. "
         "Detail quality praised by client. Promoted to lead for the next bridal batch."),
        (ARJUN_ID, "seed-perf-arjun-01",
         "Consistent accuracy in pattern cutting across all March orders. "
         "Zero fabric wastage reported this month."),
        (MEENA_ID, "seed-perf-mohan-01",
         "High-quality applique work on six blouse sets for the exhibition order. "
         "Finished early and assisted Sunil with dupatta backing."),
        (KIRAN_ID, "seed-perf-kiran-01",
         "Outstanding customer consultation for the Kapoor family bridal collection. "
         "Prepared full lookbook with fabric swatches and design sketches. "
         "Client confirmed order on the same visit."),
    ]

    for uid, log_id, note in logs:
        doc = {
            "log_id":     log_id,
            "note":       note,
            "created_at": TS,
            "created_by": ADMIN_ID,
        }
        (db.collection("staff")
           .document(uid)
           .collection("performance_logs")
           .document(log_id)
           .set(doc))
        total += 1

    print(f"  Created {total} performance log(s) across {len(ACTIVE_STAFF)} staff")


# =============================================================================
#  Seed: Work Gallery (sub-collection of staff)
# =============================================================================

def seed_work_gallery() -> None:
    """
    Seed work gallery images for each active staff member.
    Path: staff/{user_id}/work_gallery/{image_id}

    Note: URLs are placeholder values; real images would be in Firebase Storage.
    In a live environment these would be signed GCS URLs via generate_signed_url().
    """
    print("\n--- Seeding work gallery ---")
    total = 0

    gallery = [
        (RAJU_ID, "seed-gallery-raju-01",
         "gallery/seed-staff-raju-mehta/bridal-lehenga-march-2026.jpg",
         "Bridal lehenga - hand finishing and button work, March 2026"),
        (RAJU_ID, "seed-gallery-raju-02",
         "gallery/seed-staff-raju-mehta/sherwani-lining-march-2026.jpg",
         "Sherwani with silk lining - Sharma family order"),
        (SUNITA_ID, "seed-gallery-sunil-01",
         "gallery/seed-staff-sunil-rao/zari-dupatta-march-2026.jpg",
         "Zari embroidery on bridal dupatta - Mehta wedding"),
        (SUNITA_ID, "seed-gallery-sunil-02",
         "gallery/seed-staff-sunil-rao/mirror-work-blouse-march-2026.jpg",
         "Mirror work blouse - exhibition order collection"),
        (ARJUN_ID, "seed-gallery-arjun-01",
         "gallery/seed-staff-arjun-das/pattern-cut-batch-march-2026.jpg",
         "Pattern cutting batch for March bridal orders"),
        (MEENA_ID, "seed-gallery-mohan-01",
         "gallery/seed-staff-mohan-kumar/applique-blouses-march-2026.jpg",
         "Applique work on blouse sets - six pieces"),
        (KIRAN_ID, "seed-gallery-kiran-01",
         "gallery/seed-staff-kiran-nair/bridal-lookbook-kapoor-march-2026.jpg",
         "Bridal lookbook - Kapoor family collection, fabric swatches and sketches"),
    ]

    for uid, img_id, storage_path, caption in gallery:
        bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "your-project.appspot.com")
        doc = {
            "image_id":     img_id,
            "image_url":    f"https://storage.googleapis.com/{bucket}/{storage_path}",
            "storage_path": storage_path,
            "caption":      caption,
            "uploaded_at":  TS,
            "uploaded_by":  ADMIN_ID,
        }
        (db.collection("staff")
           .document(uid)
           .collection("work_gallery")
           .document(img_id)
           .set(doc))
        total += 1

    print(f"  Created {total} gallery image(s) across {len(ACTIVE_STAFF)} staff")


# =============================================================================
#  Entry point
# =============================================================================

def main() -> None:
    print("\n" + "=" * 60)
    print("  Infinity Designer Boutique - Test Data Seeder")
    print("=" * 60)

    days = _week_dates()
    print(f"\nCurrent week : {days['curr_mon']}  to  {days['curr_sat']}")
    print(f"Previous week: {days['prev_mon']}  to  {days['prev_sat']}")
    print(f"Today (IST)  : {days['today']}")

    # Step 1: wipe everything
    delete_all()

    # Step 2: seed in dependency order
    # (admins first so created_by references are valid conceptually)
    seed_admins()
    seed_staff()
    seed_attendance(days)
    seed_financial_requests(days)
    seed_overtime_records(days)
    seed_settlements(days)
    seed_performance_logs()
    seed_work_gallery()

    # Step 3: print login reference table
    print("\n" + "=" * 60)
    print("  Seed complete. Login credentials:")
    print("=" * 60)
    creds = [
        ("Owner (root admin)",    "9999999999", "0000", "admin"),
        ("Vijay Sharma (admin)",  "9876543210", "1234", "admin"),
        ("Raju Mehta",            "9123456789", "5678", "staff - active  [weekly]"),
        ("Sunil Rao",             "9234567890", "4321", "staff - active  [weekly]"),
        ("Arjun Das",             "9345678901", "9999", "staff - active  [weekly]"),
        ("Mohan Kumar",           "9456789012", "1111", "staff - active  [weekly]"),
        ("Kiran Nair",            "9678901234", "2222", "staff - active  [monthly - designer]"),
        ("Deepak Kumar",          "9567890123", "0000", "staff - INACTIVE"),
    ]
    for name, phone, pin, role in creds:
        print(f"  {name:<28}  {phone}  PIN: {pin}  ({role})")
    print()


if __name__ == "__main__":
    main()
