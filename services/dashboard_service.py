"""
services/dashboard_service.py - Dashboard aggregation logic.

PostgreSQL-backed dashboard summaries and analytics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from services.repositories.attendance_repository import get_attendance_repository
from services.repositories.financial_repository import get_financial_repository
from services.repositories.leave_repository import get_leave_repository
from services.repositories.overtime_repository import get_overtime_repository
from utils.logger import get_logger
from utils.timezone_utils import today_ist, period_range

log = get_logger(__name__)


def _to_date(value) -> date | None:
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
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _attendance_repo():
    return get_attendance_repository()


def _financial_repo():
    return get_financial_repository()


def _leave_repo():
    return get_leave_repository()


def _overtime_repo():
    return get_overtime_repository()


def get_daily_summary(target_date: date | None = None) -> dict:
    if target_date is None:
        target_date = today_ist()

    from services.user_service import list_staff
    from services.leave_service import get_leaves_for_date, get_pending_leave_count
    from services.settings_service import get_working_config

    active_staff = list_staff(status_filter="active")
    total_active = len(active_staff)
    active_staff_ids = {s.get("user_id") for s in active_staff if s.get("user_id")}

    on_leave_today_all = get_leaves_for_date(target_date)
    on_leave_today = [lv for lv in on_leave_today_all if lv.get("user_id") in active_staff_ids]
    on_leave_user_ids = {lv.get("user_id") for lv in on_leave_today if lv.get("user_id")}
    on_leave_names = [lv.get("staff_name", "") for lv in on_leave_today if lv.get("staff_name")]
    pending_leave = get_pending_leave_count()

    repo = _attendance_repo()
    today_rows = repo.list_by_date(target_date)
    attendance_by_user = {r.get("user_id"): r for r in today_rows if r.get("user_id")}

    punched_in = 0
    punched_out = 0
    still_in = 0
    today_attendance: list[dict] = []
    present_names: list[str] = []
    still_working_names: list[str] = []
    absent_names: list[str] = []
    absent_staff: list[dict] = []

    for staff in active_staff:
        uid = staff["user_id"]
        rec = attendance_by_user.get(uid)
        if rec:
            punched_in += 1
            full_name = staff.get("full_name", "")
            if full_name:
                present_names.append(full_name)
            if rec.get("status") == "out":
                punched_out += 1
            else:
                still_in += 1
                if full_name:
                    still_working_names.append(full_name)
            today_attendance.append(
                {
                    "user_id": uid,
                    "full_name": full_name,
                    "designation": staff.get("designation", ""),
                    "punch_in_time": rec.get("punch_in"),
                    "punch_out_time": rec.get("punch_out"),
                    "duration_minutes": rec.get("duration_minutes"),
                    "status": rec.get("status", "in"),
                    "standard_login_time": staff.get("standard_login_time", "09:30"),
                    "standard_logout_time": staff.get("standard_logout_time", "18:30"),
                }
            )
        elif uid not in on_leave_user_ids:
            full_name = staff.get("full_name", "")
            if full_name:
                absent_names.append(full_name)
            absent_staff.append(
                {
                    "user_id": uid,
                    "full_name": full_name,
                    "designation": staff.get("designation", ""),
                }
            )

    absent = total_active - punched_in
    unexpected_absent = len(absent_staff)

    pending_financial_count = _financial_repo().count_requests({"status": "pending"})
    pending_overtime_count = _overtime_repo().count_pending()

    late_arrivals = []
    for att in today_attendance:
        std_time = att.get("standard_login_time", "10:00")
        punch_in = att.get("punch_in_time")
        if not punch_in or not std_time:
            continue
        try:
            if isinstance(punch_in, str):
                pi_dt = datetime.fromisoformat(punch_in.replace("Z", "+00:00"))
            else:
                pi_dt = punch_in
            std_h, std_m = map(int, std_time.split(":"))
            grace_minutes = 15
            late_threshold = std_h * 60 + std_m + grace_minutes
            actual_minutes = pi_dt.hour * 60 + pi_dt.minute
            if actual_minutes > late_threshold:
                late_arrivals.append(
                    {
                        "full_name": att.get("full_name", ""),
                        "designation": att.get("designation", ""),
                        "minutes_late": actual_minutes - (std_h * 60 + std_m),
                    }
                )
        except Exception:
            continue

    working_config = get_working_config() or {}
    standard_hours_per_day = float(working_config.get("standard_hours_per_day", 8) or 8)
    overtime_grace_minutes = int(working_config.get("overtime_grace_minutes", 30) or 30)

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
        "pending_financial_requests": pending_financial_count,
        "pending_overtime_approvals": pending_overtime_count,
        "pending_leave_requests": pending_leave,
        "total_pending_approvals": pending_financial_count + pending_overtime_count + pending_leave,
        "today_attendance": today_attendance,
        "standard_hours_per_day": standard_hours_per_day,
        "overtime_grace_minutes": overtime_grace_minutes,
    }

    log.info(
        "Daily summary generated | date=%s | staff=%d | present=%d",
        target_date,
        total_active,
        punched_in,
    )
    return summary


def get_financial_summary(start_date: date, end_date: date) -> dict:
    docs = _financial_repo().list_requests(
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )

    total_expenses = 0.0
    total_advances = 0.0
    approved_expenses = 0.0
    approved_advances = 0.0
    pending_count = 0
    approved_count = 0
    rejected_count = 0
    reimbursement_pending_count = 0
    reimbursement_pending_amount = 0.0

    for data in docs:
        amount = float(data.get("amount", 0) or 0)
        req_type = data.get("type", "")
        status = data.get("status", "")

        if req_type == "shop_expense":
            total_expenses += amount
            if status == "approved":
                approved_expenses += amount
                if data.get("reimbursement_status") != "paid":
                    reimbursement_pending_count += 1
                    reimbursement_pending_amount += amount
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
        "reimbursement_pending_count": reimbursement_pending_count,
        "reimbursement_pending_amount": round(reimbursement_pending_amount, 2),
    }

    log.info(
        "Financial summary | period=%s to %s | expenses=%.2f | advances=%.2f",
        start_date,
        end_date,
        total_expenses,
        total_advances,
    )
    return summary


def get_attendance_summary(start_date: date, end_date: date) -> dict:
    from services.user_service import list_staff
    from utils.timezone_utils import minutes_to_hhmm

    active_staff = list_staff(status_filter="active")
    active_staff_ids = [s.get("user_id") for s in active_staff if s.get("user_id")]
    all_records = _attendance_repo().list_by_users_between(active_staff_ids, start_date, end_date)

    attendance_by_user = defaultdict(lambda: {"days_present": 0, "total_minutes": 0})
    for rec in all_records:
        uid = rec.get("user_id")
        if not uid:
            continue
        if rec.get("punch_in"):
            attendance_by_user[uid]["days_present"] += 1
        attendance_by_user[uid]["total_minutes"] += int(rec.get("duration_minutes") or 0)

    staff_summaries = []
    total_days_present = 0
    total_minutes = 0

    for staff in active_staff:
        uid = staff["user_id"]
        metrics = attendance_by_user.get(uid, {"days_present": 0, "total_minutes": 0})
        days = metrics["days_present"]
        mins = metrics["total_minutes"]

        staff_summaries.append(
            {
                "user_id": uid,
                "full_name": staff.get("full_name", ""),
                "designation": staff.get("designation", ""),
                "days_present": days,
                "total_minutes": mins,
                "total_duration": minutes_to_hhmm(mins),
            }
        )

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

    log.info(
        "Attendance summary | period=%s to %s | staff=%d | total_days=%d",
        start_date,
        end_date,
        len(active_staff),
        total_days_present,
    )
    return summary


def get_dashboard_analytics() -> dict:
    from services.user_service import list_staff

    attendance_trend = []
    today = today_ist()
    active_staff = list_staff(status_filter="active")
    active_staff_ids = [s.get("user_id") for s in active_staff if s.get("user_id")]
    total_active = len(active_staff)
    repo = _attendance_repo()

    trend_start = today - timedelta(days=6)
    trend_rows = repo.list_by_users_between(active_staff_ids, trend_start, today)
    present_by_date: dict[str, set[str]] = defaultdict(set)
    for row in trend_rows:
        row_date = row.get("date")
        row_user_id = row.get("user_id")
        if row_date and row_user_id:
            present_by_date[str(row_date)].add(str(row_user_id))

    for i in range(6, -1, -1):
        check_date = today - timedelta(days=i)
        present = len(present_by_date.get(check_date.isoformat(), set()))
        attendance_trend.append(
            {
                "date": check_date.strftime("%Y-%m-%d"),
                "day": check_date.strftime("%a"),
                "present": present,
                "absent": total_active - present,
                "total": total_active,
            }
        )

    start, end = period_range("monthly")
    financial_summary = get_financial_summary(start, end)

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
        key = d.isoformat()
        row = {"date": key, "day": d.strftime("%d %b"), "requested": 0, "approved": 0}
        leave_trend.append(row)
        leave_trend_index[key] = row

    for lv in _leave_repo().list_requests({}):
        status = lv.get("status")
        leave_type = lv.get("leave_type")
        created_date = _to_date(lv.get("created_at"))
        reviewed_date = _to_date(lv.get("reviewed_at"))

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
            "reimbursement_pending_count": financial_summary["reimbursement_pending_count"],
            "reimbursement_pending_amount": financial_summary["reimbursement_pending_amount"],
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
