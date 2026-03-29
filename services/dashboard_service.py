"""
services/dashboard_service.py - Dashboard aggregation logic.

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
    active_staff_ids = {s.get("user_id") for s in active_staff if s.get("user_id")}

    # On leave today (active staff only)
    from services.leave_service import get_leaves_for_date, get_pending_leave_count
    on_leave_today_all = get_leaves_for_date(target_date)
    on_leave_today = [
        lv for lv in on_leave_today_all
        if lv.get("user_id") in active_staff_ids
    ]
    on_leave_user_ids = {lv.get("user_id") for lv in on_leave_today if lv.get("user_id")}
    on_leave_names = [lv.get("staff_name", "") for lv in on_leave_today if lv.get("staff_name")]
    pending_leave = get_pending_leave_count()

    # Count who punched in today
    doc_id = date_to_doc_id(target_date)
    punched_in = 0
    punched_out = 0
    still_in = 0
    today_attendance = []
    present_names = []
    still_working_names = []
    absent_names = []
    absent_staff = []
    for staff in active_staff:
        uid = staff["user_id"]
        rec = db.collection("attendance").document(uid).collection("records").document(doc_id).get()
        if rec.exists:
            data = rec.to_dict()
            punched_in += 1
            full_name = staff.get("full_name", "")
            if full_name:
                present_names.append(full_name)
            if data.get("status") == "out":
                punched_out += 1
            else:
                still_in += 1
                if full_name:
                    still_working_names.append(full_name)
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
        elif uid not in on_leave_user_ids:
            full_name = staff.get("full_name", "")
            if full_name:
                absent_names.append(full_name)
            absent_staff.append({
                "user_id": uid,
                "full_name": full_name,
                "designation": staff.get("designation", ""),
            })

    absent = total_active - punched_in
    unexpected_absent = len(absent_staff)

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

    # Late arrivals (punched in after standard login time + 15 min grace)
    late_arrivals = []
    for att in today_attendance:
        std_time = att.get("standard_login_time", "10:00")
        punch_in = att.get("punch_in_time")
        if punch_in and std_time:
            try:
                import pytz
                IST = pytz.timezone("Asia/Kolkata")
                pi_ist = punch_in.astimezone(IST) if hasattr(punch_in, "astimezone") else punch_in
                std_h, std_m = map(int, std_time.split(":"))
                from datetime import time as dt_time
                grace_minutes = 15
                late_threshold = std_h * 60 + std_m + grace_minutes
                actual_minutes = pi_ist.hour * 60 + pi_ist.minute
                if actual_minutes > late_threshold:
                    late_arrivals.append({
                        "full_name": att.get("full_name", ""),
                        "designation": att.get("designation", ""),
                        "minutes_late": actual_minutes - (std_h * 60 + std_m),
                    })
            except Exception:
                pass

    summary = {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_active_staff": total_active,
        "punched_in": punched_in,
        "punched_out": punched_out,
        "still_working": still_in,
        "present_names": present_names,
        "still_working_names": still_working_names,
        "absent": absent,
        "absent_names": absent_names,
        "absent_staff": absent_staff,
        "unexpected_absent": unexpected_absent,
        "on_leave": len(on_leave_today),
        "on_leave_names": on_leave_names,
        "on_leave_details": on_leave_today,
        "late_arrivals": late_arrivals,
        "late_count": len(late_arrivals),
        "pending_financial_requests": len(pending_financial),
        "pending_overtime_approvals": len(pending_overtime),
        "pending_leave_requests": pending_leave,
        "total_pending_approvals": len(pending_financial) + len(pending_overtime) + pending_leave,
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


def get_dashboard_analytics() -> dict:
    """
    Get analytics data for dashboard charts.

    Returns:
      - 7-day attendance trend (for line chart)
      - Financial overview (for doughnut chart)
      - Staff distribution by designation (for bar chart)
    """
    from datetime import datetime, timedelta
    from collections import Counter
    import pytz
    from services.user_service import list_staff

    log.debug("get_dashboard_analytics")
    db = get_firestore()

    # -- 7-day attendance trend --
    attendance_trend = []
    today = today_ist()
    active_staff = list_staff(status_filter="active")
    total_active = len(active_staff)

    for i in range(6, -1, -1):  # 6 days ago to today
        check_date = today - timedelta(days=i)
        doc_id = date_to_doc_id(check_date)
        present = 0
        for staff in active_staff:
            rec = db.collection("attendance").document(staff["user_id"]).collection("records").document(doc_id).get()
            if rec.exists:
                present += 1
        attendance_trend.append({
            "date": check_date.strftime("%Y-%m-%d"),
            "day": check_date.strftime("%a"),
            "present": present,
            "absent": total_active - present,
            "total": total_active,
        })

    # -- Financial overview (this month) --
    start, end = period_range("monthly")
    financial_summary = get_financial_summary(start, end)

    # -- Leave overview (this month) + trend (last 14 days) --
    IST = pytz.timezone("Asia/Kolkata")
    leave_docs = list(db.collection("leave_requests").stream())

    def _to_ist_date(value):
        if not value:
            return None
        if hasattr(value, "astimezone"):
            return value.astimezone(IST).date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(IST).date()
            except ValueError:
                return None
        return None

    leave_status_counts = {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "cancelled": 0,
    }
    leave_type_counts = {
        "half_day": 0,
        "full_day": 0,
        "multiple_days": 0,
    }
    approved_leave_days = 0.0

    trend_days = 14
    trend_start = today - timedelta(days=trend_days - 1)
    leave_trend = []
    leave_trend_index = {}
    for i in range(trend_days):
        d = trend_start + timedelta(days=i)
        k = d.isoformat()
        row = {
            "date": k,
            "day": d.strftime("%d %b"),
            "requested": 0,
            "approved": 0,
        }
        leave_trend.append(row)
        leave_trend_index[k] = row

    for leave_doc in leave_docs:
        lv = leave_doc.to_dict()
        status = lv.get("status")
        leave_type = lv.get("leave_type")
        created_date = _to_ist_date(lv.get("created_at"))
        reviewed_date = _to_ist_date(lv.get("reviewed_at"))

        if created_date and start <= created_date <= end:
            if status in leave_status_counts:
                leave_status_counts[status] += 1
            if leave_type in leave_type_counts:
                leave_type_counts[leave_type] += 1
            if status == "approved":
                approved_leave_days += float(lv.get("total_days") or 0.0)

        if created_date and trend_start <= created_date <= today:
            row = leave_trend_index.get(created_date.isoformat())
            if row:
                row["requested"] += 1

        if status == "approved" and reviewed_date and trend_start <= reviewed_date <= today:
            row = leave_trend_index.get(reviewed_date.isoformat())
            if row:
                row["approved"] += 1

    # -- Staff distribution by designation --
    designation_counts = Counter(s.get("designation", "Other") for s in active_staff)
    staff_distribution = [
        {"designation": k, "count": v}
        for k, v in sorted(designation_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "attendance_trend": attendance_trend,
        "financial_overview": {
            "total_expenses": financial_summary["total_expenses"],
            "approved_expenses": financial_summary["approved_expenses"],
            "total_advances": financial_summary["total_advances"],
            "approved_advances": financial_summary["approved_advances"],
            "pending_count": financial_summary["pending_count"],
            "approved_count": financial_summary["approved_count"],
            "rejected_count": financial_summary["rejected_count"],
        },
        "leave_overview": {
            "pending_count": leave_status_counts["pending"],
            "approved_count": leave_status_counts["approved"],
            "rejected_count": leave_status_counts["rejected"],
            "cancelled_count": leave_status_counts["cancelled"],
            "approved_days": round(approved_leave_days, 1),
            "half_day_count": leave_type_counts["half_day"],
            "full_day_count": leave_type_counts["full_day"],
            "multiple_days_count": leave_type_counts["multiple_days"],
            "total_requests": sum(leave_status_counts.values()),
        },
        "leave_trend": leave_trend,
        "staff_distribution": staff_distribution,
        "total_active_staff": total_active,
    }

