"""
services/overtime_service.py - Overtime detection and management.

PostgreSQL table: overtime_records

Overtime is auto-detected after punch-out when the worked duration
exceeds shift hours + overtime_grace_minutes (from settings).
"""
from __future__ import annotations

import uuid

from services.repositories.overtime_repository import get_overtime_repository
from services.requester_context import build_requester_context_map
from services.settings_service import get_working_config
from utils.logger import get_logger, audit_log
from utils.timezone_utils import format_ist, now_utc

log = get_logger(__name__)


def _repo():
    return get_overtime_repository()


def _db_timestamp():
    return now_utc()


def _attach_requester_context(data: dict, context_map: dict[str, dict] | None = None) -> dict:
    """Attach requester profile fields used by admin approval cards."""
    out = dict(data)
    uid = out.get("user_id")

    requester_name = "Unknown Staff"
    requester_phone = ""
    requester_role = "staff"
    requester_designation = ""

    if uid and context_map:
        ctx = context_map.get(str(uid))
        if ctx:
            requester_name = ctx.get("requester_name") or requester_name
            requester_phone = ctx.get("requester_phone") or ""
            requester_role = ctx.get("requester_role") or "staff"
            requester_designation = ctx.get("requester_designation") or ""

    out["requester_user_id"] = uid
    out["requester_name"] = requester_name
    out["requester_phone"] = requester_phone
    out["requester_role"] = requester_role
    out["requester_designation"] = requester_designation

    # Backward-compatible aliases used by templates.
    out["staff_name"] = requester_name
    out["full_name"] = requester_name

    return out


def calculate_hourly_rate(salary: float, salary_type: str = "weekly") -> float:
    """
    Calculate hourly rate from weekly salary.

    weekly_salary / working_days_per_week / standard_hours_per_day
    """
    working_config = get_working_config()
    hours = working_config["standard_hours_per_day"]
    if hours <= 0:
        log.warning("Invalid config: standard_hours_per_day=%d", hours)
        return 0.0

    days = working_config["working_days_per_week"]
    if days <= 0:
        log.warning("Invalid config: working_days_per_week=%d", days)
        return 0.0
    rate = salary / days / hours
    log.info("calculate_hourly_rate | weekly_salary=%.2f | days=%d | hours=%d | rate=%.2f",
             salary, days, hours, rate)
    return rate


def detect_overtime(user_id: str, attendance_record: dict) -> dict | None:
    """
    Called after punch-out. Checks if the worked duration exceeds
    shift hours + grace period, and if so creates an overtime record.

    Returns the overtime record dict, or None if no overtime.
    """
    working_config = get_working_config()
    duration_minutes = attendance_record.get("duration_minutes", 0)

    # Prefer explicit shift times from app config (default_login_time/default_logout_time)
    # so overtime is computed relative to the actual configured shift window.
    try:
        from services.settings_service import get_app_config
        app_cfg = get_app_config()
        std_login = app_cfg.get("default_login_time")
        std_logout = app_cfg.get("default_logout_time")
    except Exception:
        std_login = None
        std_logout = None

    def _minutes_from_hhmm(s: str) -> int:
        h, m = 0, 0
        try:
            parts = str(s).split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            return 0
        return h * 60 + m

    shift_minutes = None
    if std_login and std_logout:
        li = _minutes_from_hhmm(std_login)
        lo = _minutes_from_hhmm(std_logout)
        # handle overnight shifts
        shift_minutes = (lo - li) % (24 * 60)
        if shift_minutes == 0:
            shift_minutes = None

    if shift_minutes is None:
        shift_minutes = working_config["standard_hours_per_day"] * 60

    grace = working_config.get("overtime_grace_minutes", 0)
    threshold = shift_minutes + grace

    if duration_minutes <= threshold:
        log.info("No overtime detected | user_id=%s | duration=%dmin | threshold=%dmin",
                 user_id, duration_minutes, threshold)
        return None

    # Subtract the shift duration and also the grace period from the overtime amount
    overtime_minutes = max(0, duration_minutes - shift_minutes - grace)
    record_date = attendance_record.get("date", "")

    from services.user_service import get_staff
    staff = get_staff(user_id)

    # Determine salary and salary_type for hourly rate calculation
    salary = float(staff.get("weekly_salary", 0)) if staff else 0
    hourly_rate = calculate_hourly_rate(salary)
    overtime_payout = round(hourly_rate * (overtime_minutes / 60), 2)

    record_id = str(uuid.uuid4())
    staff_name = staff.get("full_name", "") if staff else ""
    ts = _db_timestamp()
    doc = {
        "record_id": record_id,
        "user_id": user_id,
        "staff_name": staff_name,
        "full_name": staff_name,
        "date": record_date,
        "total_worked_minutes": duration_minutes,
        "overtime_minutes": overtime_minutes,
        "hourly_rate": hourly_rate,
        "calculated_payout": overtime_payout,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": ts,
        "updated_at": ts,
    }

    _repo().save(record_id, doc)

    log.info("Overtime detected | user_id=%s | date=%s | overtime_minutes=%d | payout=%.2f",
             user_id, record_date, overtime_minutes, overtime_payout)
    audit_log(user_id, "OVERTIME_DETECTED", f"overtime_records/{record_id}",
              f"minutes={overtime_minutes}, payout={overtime_payout}")
    return doc


from services.attendance_service import _repo as attendance_repo

def get_pending_overtime() -> list[dict]:
    """List all overtime records awaiting admin approval, with punch_in/punch_out."""
    rows = _repo().list_pending()
    context_map = build_requester_context_map(d.get("user_id") for d in rows)
    # Collect all (user_id, date) pairs
    user_date_pairs = set((d.get("user_id"), d.get("date")) for d in rows)
    user_ids = list({uid for uid, _ in user_date_pairs if uid})
    dates = [dt for _, dt in user_date_pairs if dt]
    if not user_ids or not dates:
        log.info("get_pending_overtime | count=0 (no users or dates)")
        return []
    min_date = min(dates)
    max_date = max(dates)
    # Batch fetch all attendance records for these users and dates
    attendance_records = attendance_repo().list_by_users_between(user_ids, min_date, max_date)
    # Build lookup: (user_id, date) -> attendance
    att_lookup = {(att["user_id"], att["date"]): att for att in attendance_records}
    result = []
    for data in rows:
        data = _attach_requester_context(data, context_map)
        data = _sanitise(data)
        att = att_lookup.get((data.get("user_id"), data.get("date")))
        if att:
            data["punch_in"] = att.get("punch_in")
            data["punch_out"] = att.get("punch_out")
        else:
            data["punch_in"] = None
            data["punch_out"] = None
        result.append(data)
    log.info("get_pending_overtime | count=%d", len(result))
    return result


def get_overtime_for_user(user_id: str) -> list[dict]:
    """Get all overtime records for a specific user, with punch_in/punch_out."""
    rows = _repo().list_for_user(user_id)
    context_map = build_requester_context_map(d.get("user_id") for d in rows)
    dates = [d.get("date") for d in rows if d.get("date")]
    if not dates:
        log.debug("get_overtime_for_user | user_id=%s | count=0 (no dates)", user_id)
        return []
    min_date = min(dates)
    max_date = max(dates)
    # Batch fetch all attendance records for this user and all relevant dates
    attendance_records = attendance_repo().list_by_user_between(user_id, min_date, max_date)
    att_lookup = {(att["user_id"], att["date"]): att for att in attendance_records}
    results = []
    for data in rows:
        data = _attach_requester_context(data, context_map)
        data = _sanitise(data)
        att = att_lookup.get((data.get("user_id"), data.get("date")))
        if att:
            data["punch_in"] = att.get("punch_in")
            data["punch_out"] = att.get("punch_out")
        else:
            data["punch_in"] = None
            data["punch_out"] = None
        results.append(data)
    log.debug("get_overtime_for_user | user_id=%s | count=%d", user_id, len(results))
    return results


def approve_overtime(overtime_id: str, admin_id: str) -> tuple[bool, str]:
    """Approve an overtime record."""
    data = _repo().record_exists(overtime_id)
    if data is None:
        return False, "Overtime record not found."
    if data.get("status") != "pending":
        return False, f"Overtime record is already {data.get('status')}."
    ts = _db_timestamp()
    _repo().update_review(overtime_id, "approved", admin_id, ts, ts)
    log.info("Overtime approved | record_id=%s | admin_id=%s", overtime_id, admin_id)
    audit_log(admin_id, "APPROVE_OVERTIME", f"overtime_records/{overtime_id}")
    return True, ""


def reject_overtime(overtime_id: str, admin_id: str) -> tuple[bool, str]:
    """Reject an overtime record."""
    data = _repo().record_exists(overtime_id)
    if data is None:
        return False, "Overtime record not found."
    if data.get("status") != "pending":
        return False, f"Overtime record is already {data.get('status')}."
    ts = _db_timestamp()
    _repo().update_review(overtime_id, "rejected", admin_id, ts, ts)
    log.info("Overtime rejected | record_id=%s | admin_id=%s", overtime_id, admin_id)
    audit_log(admin_id, "REJECT_OVERTIME", f"overtime_records/{overtime_id}")
    return True, ""


def get_approved_overtime_for_period(user_id: str, start, end) -> list[dict]:
    """Return approved overtime records for a user within a date range."""
    results = _repo().get_approved_for_period(user_id, start, end)
    log.debug("get_approved_overtime_for_period | user_id=%s | start=%s | end=%s | count=%d",
              user_id, start, end, len(results))
    return results


# -- Helper --------------------------------------------------------------------

def _sanitise(data: dict) -> dict:
    """Convert timestamp fields to IST strings."""
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
