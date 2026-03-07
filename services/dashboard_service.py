"""
services/dashboard_service.py – Dashboard aggregation logic.

Provides summary data for the admin dashboard:
  - Daily summary (attendance count, pending requests, etc.)
  - Financial summary by period
  - Attendance summary by period
"""
from __future__ import annotations

from datetime import date

from utils.firebase_client import get_firestore
from utils.logger import get_logger
from utils.timezone_utils import today_ist, today_ist_str, period_range, date_to_doc_id

log = get_logger(__name__)


def get_daily_summary(target_date: date | None = None) -> dict:
    """
    Get a snapshot summary for a given date (defaults to today IST).

    Returns counts of attendance, pending financial requests, pending overtime, etc.
    """
    if target_date is None:
        target_date = today_ist()

    log.debug("get_daily_summary | target_date=%s", target_date)
    db = get_firestore()
    from services.user_service import list_staff

    active_staff = list_staff(status_filter="active")
    total_active = len(active_staff)

    # Count who punched in today
    doc_id = date_to_doc_id(target_date)
    punched_in = 0
    punched_out = 0
    still_in = 0
    today_attendance = []
    for staff in active_staff:
        uid = staff["user_id"]
        rec = db.collection("attendance").document(uid).collection("records").document(doc_id).get()
        if rec.exists:
            data = rec.to_dict()
            punched_in += 1
            if data.get("status") == "out":
                punched_out += 1
            else:
                still_in += 1
            today_attendance.append({
                "user_id": uid,
                "full_name": staff.get("full_name", ""),
                "designation": staff.get("designation", ""),
                "punch_in_time": data.get("punch_in"),
                "punch_out_time": data.get("punch_out"),
                "duration_minutes": data.get("duration_minutes"),
                "status": data.get("status", "in"),
                "standard_login_time": staff.get("standard_login_time", "09:30"),
                "standard_logout_time": staff.get("standard_logout_time", "18:30"),
            })

    absent = total_active - punched_in

    # Pending financial requests
    pending_financial = list(
        db.collection("financial_requests")
        .where("status", "==", "pending")
        .stream()
    )

    # Pending overtime
    pending_overtime = list(
        db.collection("overtime_records")
        .where("status", "==", "pending")
        .stream()
    )

    summary = {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_active_staff": total_active,
        "punched_in": punched_in,
        "punched_out": punched_out,
        "still_working": still_in,
        "absent": absent,
        "pending_financial_requests": len(pending_financial),
        "pending_overtime_approvals": len(pending_overtime),
        "today_attendance": today_attendance,
    }

    log.info("Daily summary generated | date=%s | staff=%d | present=%d",
             target_date, total_active, punched_in)
    return summary


def get_financial_summary(start_date: date, end_date: date) -> dict:
    """
    Get a financial breakdown for the given date range.

    Returns aggregated amounts by type and status.
    """
    log.debug("get_financial_summary | start_date=%s | end_date=%s", start_date, end_date)
    db = get_firestore()
    import pytz
    from datetime import datetime

    IST = pytz.timezone("Asia/Kolkata")

    docs = db.collection("financial_requests").stream()

    total_expenses = 0.0
    total_advances = 0.0
    approved_expenses = 0.0
    approved_advances = 0.0
    pending_count = 0
    approved_count = 0
    rejected_count = 0

    for d in docs:
        data = d.to_dict()
        created = data.get("created_at")
        if not created or not hasattr(created, "astimezone"):
            continue

        doc_date = created.astimezone(IST).date()
        if not (start_date <= doc_date <= end_date):
            continue

        amount = float(data.get("amount", 0))
        req_type = data.get("type", "")
        status = data.get("status", "")

        if req_type == "shop_expense":
            total_expenses += amount
            if status == "approved":
                approved_expenses += amount
        elif req_type == "personal_advance":
            total_advances += amount
            if status == "approved":
                approved_advances += amount

        if status == "pending":
            pending_count += 1
        elif status == "approved":
            approved_count += 1
        elif status == "rejected":
            rejected_count += 1

    summary = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_expenses": round(total_expenses, 2),
        "approved_expenses": round(approved_expenses, 2),
        "total_advances": round(total_advances, 2),
        "approved_advances": round(approved_advances, 2),
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
    }

    log.info("Financial summary | period=%s to %s | expenses=%.2f | advances=%.2f",
             start_date, end_date, total_expenses, total_advances)
    return summary


def get_attendance_summary(start_date: date, end_date: date) -> dict:
    """
    Get attendance analytics for the given date range across all active staff.
    """
    from services.user_service import list_staff
    from services.attendance_service import get_attendance_history
    from utils.timezone_utils import minutes_to_hhmm

    log.debug("get_attendance_summary | start_date=%s | end_date=%s", start_date, end_date)
    active_staff = list_staff(status_filter="active")
    staff_summaries = []
    total_days_present = 0
    total_minutes = 0

    for staff in active_staff:
        uid = staff["user_id"]
        records = get_attendance_history(uid, start_date, end_date)
        days = sum(1 for r in records if r.get("punch_in"))
        mins = sum(r.get("duration_minutes", 0) for r in records)

        staff_summaries.append({
            "user_id": uid,
            "full_name": staff.get("full_name", ""),
            "designation": staff.get("designation", ""),
            "days_present": days,
            "total_minutes": mins,
            "total_duration": minutes_to_hhmm(mins),
        })

        total_days_present += days
        total_minutes += mins

    summary = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_staff": len(active_staff),
        "total_days_present": total_days_present,
        "total_minutes": total_minutes,
        "total_duration": minutes_to_hhmm(total_minutes),
        "staff_summaries": staff_summaries,
    }

    log.info("Attendance summary | period=%s to %s | staff=%d | total_days=%d",
             start_date, end_date, len(active_staff), total_days_present)
    return summary
