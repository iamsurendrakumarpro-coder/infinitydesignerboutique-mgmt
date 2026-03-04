"""
services/overtime_service.py – Overtime detection and management.

Firestore collection: overtime_records/{record_id}

Overtime is auto-detected after punch-out when the worked duration
exceeds shift hours + OVERTIME_GRACE_MINUTES.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from config import get_config
from utils.firebase_client import get_firestore
from utils.logger import get_logger, audit_log
from utils.timezone_utils import format_ist

log = get_logger(__name__)

_COLLECTION = "overtime_records"


def calculate_hourly_rate(weekly_salary: float) -> float:
    """Calculate hourly rate: weekly_salary / working_days / hours_per_day."""
    cfg = get_config()
    days = cfg.WORKING_DAYS_PER_WEEK
    hours = cfg.STANDARD_HOURS_PER_DAY
    if days <= 0 or hours <= 0:
        return 0.0
    return weekly_salary / days / hours


def detect_overtime(user_id: str, attendance_record: dict) -> dict | None:
    """
    Called after punch-out. Checks if the worked duration exceeds
    shift hours + grace period, and if so creates an overtime record.

    Returns the overtime record dict, or None if no overtime.
    """
    cfg = get_config()
    duration_minutes = attendance_record.get("duration_minutes", 0)

    shift_minutes = cfg.STANDARD_HOURS_PER_DAY * 60
    threshold = shift_minutes + cfg.OVERTIME_GRACE_MINUTES

    if duration_minutes <= threshold:
        log.info("No overtime detected | user_id=%s | duration=%dmin | threshold=%dmin",
                 user_id, duration_minutes, threshold)
        return None

    overtime_minutes = duration_minutes - shift_minutes
    record_date = attendance_record.get("date", "")

    from services.user_service import get_staff
    staff = get_staff(user_id)
    weekly_salary = float(staff.get("weekly_salary", 0)) if staff else 0
    hourly_rate = calculate_hourly_rate(weekly_salary)
    overtime_payout = round(hourly_rate * (overtime_minutes / 60), 2)

    record_id = str(uuid.uuid4())
    doc = {
        "record_id": record_id,
        "user_id": user_id,
        "date": record_date,
        "total_worked_minutes": duration_minutes,
        "overtime_minutes": overtime_minutes,
        "hourly_rate": hourly_rate,
        "calculated_payout": overtime_payout,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    }

    db = get_firestore()
    db.collection(_COLLECTION).document(record_id).set(doc)

    log.info("Overtime detected | user_id=%s | date=%s | overtime_minutes=%d | payout=%.2f",
             user_id, record_date, overtime_minutes, overtime_payout)
    audit_log(user_id, "OVERTIME_DETECTED", f"{_COLLECTION}/{record_id}",
              f"minutes={overtime_minutes}, payout={overtime_payout}")
    return doc


def get_pending_overtime() -> list[dict]:
    """List all overtime records awaiting admin approval."""
    db = get_firestore()
    docs = (
        db.collection(_COLLECTION)
        .where("status", "==", "pending")
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )
    result = [_sanitise(d.to_dict()) for d in docs]
    log.info("get_pending_overtime | count=%d", len(result))
    return result


def get_overtime_for_user(user_id: str) -> list[dict]:
    """Get all overtime records for a specific user."""
    db = get_firestore()
    docs = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )
    return [_sanitise(d.to_dict()) for d in docs]


def approve_overtime(overtime_id: str, admin_id: str) -> tuple[bool, str]:
    """Approve an overtime record."""
    db = get_firestore()
    ref = db.collection(_COLLECTION).document(overtime_id)
    doc = ref.get()
    if not doc.exists:
        return False, "Overtime record not found."

    data = doc.to_dict()
    if data.get("status") != "pending":
        return False, f"Overtime record is already {data.get('status')}."

    ref.update({
        "status": "approved",
        "reviewed_by": admin_id,
        "reviewed_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    })
    log.info("Overtime approved | record_id=%s | admin_id=%s", overtime_id, admin_id)
    audit_log(admin_id, "APPROVE_OVERTIME", f"{_COLLECTION}/{overtime_id}")
    return True, ""


def reject_overtime(overtime_id: str, admin_id: str) -> tuple[bool, str]:
    """Reject an overtime record."""
    db = get_firestore()
    ref = db.collection(_COLLECTION).document(overtime_id)
    doc = ref.get()
    if not doc.exists:
        return False, "Overtime record not found."

    data = doc.to_dict()
    if data.get("status") != "pending":
        return False, f"Overtime record is already {data.get('status')}."

    ref.update({
        "status": "rejected",
        "reviewed_by": admin_id,
        "reviewed_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    })
    log.info("Overtime rejected | record_id=%s | admin_id=%s", overtime_id, admin_id)
    audit_log(admin_id, "REJECT_OVERTIME", f"{_COLLECTION}/{overtime_id}")
    return True, ""


def get_approved_overtime_for_period(user_id: str, start, end) -> list[dict]:
    """Return approved overtime records for a user within a date range."""
    db = get_firestore()
    docs = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .where("status", "==", "approved")
        .stream()
    )
    results = []
    for d in docs:
        data = d.to_dict()
        record_date_str = data.get("date", "")
        if record_date_str:
            try:
                record_date = datetime.strptime(record_date_str, "%Y-%m-%d").date()
                if start <= record_date <= end:
                    results.append(data)
            except (ValueError, TypeError):
                pass
    return results


# ── Helper ────────────────────────────────────────────────────────────────────

def _sanitise(data: dict) -> dict:
    """Convert Firestore timestamps to IST strings."""
    out = dict(data)
    for field in ("created_at", "updated_at", "reviewed_at"):
        val = out.get(field)
        if val is None:
            out[field] = None
        elif hasattr(val, "isoformat"):
            out[field] = format_ist(val)
        else:
            try:
                out[field] = format_ist(val)
            except Exception:
                out[field] = str(val)
    return out
