"""
services/attendance_service.py - Attendance business logic.

Firestore structure
-------------------
attendance/{user_id}/records/{YYYYMMDD}

Record document::

    {
        "user_id":          str,
        "date":             "YYYY-MM-DD" (IST),
        "punch_in":         Timestamp (UTC, IST-intended),
        "punch_out":        Timestamp | None,
        "status":           "in" | "out",
        "duration_minutes": int (0 if still in),
        "created_at":       Timestamp,
        "updated_at":       Timestamp,
    }

Rules
-----
* One record per user per IST date.
* Cannot punch-in twice without punching out.
* Duration is calculated on punch-out.
"""
from __future__ import annotations

import os
from datetime import date

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from services.repositories.attendance_repository import get_attendance_repository
from utils.logger import get_logger, audit_log
from utils.timezone_utils import (
    now_utc,
    today_ist,
    today_ist_str,
    date_to_doc_id,
    period_range,
    duration_minutes,
    format_ist,
    minutes_to_hhmm,
)

log = get_logger(__name__)


def _repo():
    return get_attendance_repository()


def _db_timestamp():
    provider = os.getenv("APP_DB_PROVIDER", "firebase").strip().lower()
    if provider == "postgres":
        return now_utc()
    return SERVER_TIMESTAMP


# -- Punch operations ----------------------------------------------------------

def punch(user_id: str) -> tuple[bool, str, dict]:
    """
    Toggle punch-in / punch-out for today.

    Returns (success, message, record_dict).
    The message describes what happened (e.g. "Punched IN", "Punched OUT").
    """
    repo = _repo()
    today = today_ist()
    today_str = today_ist_str()
    doc_id = date_to_doc_id(today)
    now = now_utc()

    data = repo.get_by_user_and_date(user_id, today)

    if not data:
        # -- First punch of the day -> Punch IN --------------------------------
        ts = _db_timestamp()
        record = {
            "record_id": doc_id,
            "user_id": user_id,
            "date": today_str,
            "punch_in": now,
            "punch_out": None,
            "status": "in",
            "duration_minutes": 0,
            "created_at": ts,
            "updated_at": ts,
        }
        repo.save(record)
        log.info("PUNCH IN | user_id=%s | time_utc=%s", user_id, now.isoformat())
        audit_log(user_id, "PUNCH_IN", f"attendance/{user_id}/records/{doc_id}")
        return True, "Punched IN", _sanitise_record(record)

    status = data.get("status", "out")

    if status == "in":
        # -- Punch OUT ---------------------------------------------------------
        punch_in_ts = data.get("punch_in")
        mins = duration_minutes(punch_in_ts, now) if punch_in_ts else 0

        data.update({
            "record_id": data.get("record_id") or doc_id,
            "punch_out": now,
            "status": "out",
            "duration_minutes": mins,
            "updated_at": _db_timestamp(),
        })
        repo.save(data)
        log.info(
            "PUNCH OUT | user_id=%s | duration_minutes=%d | time_utc=%s",
            user_id, mins, now.isoformat(),
        )
        audit_log(user_id, "PUNCH_OUT", f"attendance/{user_id}/records/{doc_id}",
                  f"duration={mins}min")

        # Auto-detect overtime after punch-out
        try:
            from services.overtime_service import detect_overtime
            attendance_record = {
                "user_id": user_id,
                "date": data.get("date", today_str),
                "duration_minutes": mins,
            }
            detect_overtime(user_id, attendance_record)
        except Exception as exc:
            log.error("Overtime detection failed | user_id=%s | error=%s", user_id, exc)

        return True, "Punched OUT", _sanitise_record(data)

    # status == "out"  ->  already punched out today
    log.warning("Double punch-out attempt blocked | user_id=%s | date=%s", user_id, today)
    return (
        False,
        "You have already completed your shift for today.",
        _sanitise_record(data),
    )


def get_today_status(user_id: str) -> dict:
    """Return today's attendance record for a user.  Empty dict if no record."""
    today = today_ist()
    doc_id = date_to_doc_id(today)
    record = _repo().get_by_user_and_date(user_id, today)
    if not record:
        log.debug("get_today_status | user_id=%s | status=not_started", user_id)
        return {"status": "not_started", "date": today_ist_str()}
    log.debug("get_today_status | user_id=%s | doc_id=%s | found=true", user_id, doc_id)
    return _sanitise_record(record)


# -- History & Analytics -------------------------------------------------------

def get_attendance_history(user_id: str, start: date, end: date) -> list[dict]:
    """Return attendance records for a user between start and end dates (inclusive)."""
    rows = _repo().list_by_user_between(user_id, start, end)
    results = [_sanitise_record(r) for r in rows]
    log.debug("get_attendance_history | user_id=%s | start=%s | end=%s | count=%d",
              user_id, start, end, len(results))
    return results


def get_staff_analytics(user_id: str, period: str) -> dict:
    """
    Return analytics for a single staff member for the given period.

    Returns::

        {
            "user_id":         str,
            "period":          str,
            "start_date":      "YYYY-MM-DD",
            "end_date":        "YYYY-MM-DD",
            "days_present":    int,
            "total_minutes":   int,
            "total_duration":  "Xh Ym",
            "records":         [record_dict, ...],
        }
    """
    start, end = period_range(period)
    records = get_attendance_history(user_id, start, end)
    days_present = sum(1 for r in records if r.get("punch_in"))
    total_mins = sum(r.get("duration_minutes", 0) for r in records)

    log.debug(
        "Analytics | user_id=%s | period=%s | days=%d | total_min=%d",
        user_id, period, days_present, total_mins,
    )
    return {
        "user_id": user_id,
        "period": period,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "days_present": days_present,
        "total_minutes": total_mins,
        "total_duration": minutes_to_hhmm(total_mins),
        "records": records,
    }


def get_all_staff_analytics(period: str) -> list[dict]:
    """
    Return analytics summary for all active staff for the given period.
    Used by the admin dashboard.
    """
    from services.user_service import list_staff
    active_staff = list_staff(status_filter="active")
    result = []
    for s in active_staff:
        uid = s["user_id"]
        analytics = get_staff_analytics(uid, period)
        analytics["full_name"] = s.get("full_name", "")
        analytics["designation"] = s.get("designation", "")
        result.append(analytics)
    log.debug("All-staff analytics | period=%s | staff_count=%d", period, len(result))
    return result


# -- Helper --------------------------------------------------------------------

def _sanitise_record(data: dict) -> dict:
    """
    Convert Firestore timestamps to ISO strings so the dict is JSON-serialisable.
    """
    out = dict(data)

    for ts_field in ("punch_in", "punch_out", "created_at", "updated_at"):
        val = out.get(ts_field)
        if val is None:
            out[ts_field] = None
        elif hasattr(val, "isoformat"):
            # already a datetime
            out[ts_field] = format_ist(val)
        else:
            try:
                # Firestore DatetimeWithNanoseconds
                out[ts_field] = format_ist(val)
            except Exception:  # noqa: BLE001
                out[ts_field] = str(val)

    return out
