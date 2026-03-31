"""
modules/dashboard/routes.py - Dashboard Blueprint.

API Routes
----------
GET /api/dashboard/summary             - Overall daily dashboard metrics
GET /api/dashboard/analytics           - Chart-ready analytics data
GET /api/dashboard/financial-summary   - Financial breakdown by period
GET /api/dashboard/attendance-summary  - Attendance analytics by period
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import manager_or_admin_required, admin_required
from services import dashboard_service
from utils.logger import get_logger
from utils.timezone_utils import period_range

log = get_logger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

_VALID_PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")


@dashboard_bp.get("/api/dashboard/summary")
@dashboard_bp.get("/api/v1/dashboard/summary")
@manager_or_admin_required
def api_daily_summary():
    """Get today's dashboard summary (or for a specific date)."""
    date_str = request.args.get("date")
    target_date = None

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

    log.info("Dashboard summary | admin_id=%s | date=%s", session["user_id"], date_str or "today")
    try:
        summary = dashboard_service.get_daily_summary(target_date)
    except Exception as exc:  # noqa: BLE001
        log.exception("Dashboard summary failed | error=%s", exc)
        summary = {
            "date": (target_date or datetime.now().date()).strftime("%Y-%m-%d"),
            "total_active_staff": 0,
            "punched_in": 0,
            "punched_out": 0,
            "still_working": 0,
            "absent": 0,
            "late_count": 0,
            "pending_financial_requests": 0,
            "pending_overtime_approvals": 0,
            "pending_leave_requests": 0,
            "total_pending_approvals": 0,
            "today_attendance": [],
        }
    if session.get("role") == "manager":
        summary["pending_financial_requests"] = 0
        summary["pending_overtime_approvals"] = 0
        summary["total_pending_approvals"] = int(summary.get("pending_leave_requests", 0) or 0)
    return jsonify({"success": True, "summary": summary})


@dashboard_bp.get("/api/dashboard/analytics")
@dashboard_bp.get("/api/v1/dashboard/analytics")
@manager_or_admin_required
def api_dashboard_analytics():
    """Get chart-ready analytics data for the dashboard."""
    log.info("Dashboard analytics | admin_id=%s", session["user_id"])
    try:
        analytics = dashboard_service.get_dashboard_analytics()
    except Exception as exc:  # noqa: BLE001
        log.exception("Dashboard analytics failed | error=%s", exc)
        analytics = {
            "attendance_trend": [],
            "financial_overview": {
                "total_expenses": 0,
                "approved_expenses": 0,
                "total_advances": 0,
                "approved_advances": 0,
                "pending_count": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "reimbursement_pending_count": 0,
                "reimbursement_pending_amount": 0,
            },
            "leave_overview": {
                "pending_count": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "cancelled_count": 0,
                "approved_days": 0,
                "half_day_count": 0,
                "full_day_count": 0,
                "multiple_days_count": 0,
                "total_requests": 0,
            },
            "leave_trend": [],
            "staff_distribution": [],
            "total_active_staff": 0,
        }
    if session.get("role") == "manager":
        analytics["financial_overview"] = {
            "total_expenses": 0,
            "approved_expenses": 0,
            "total_advances": 0,
            "approved_advances": 0,
            "pending_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "reimbursement_pending_count": 0,
            "reimbursement_pending_amount": 0,
        }
    return jsonify({"success": True, "analytics": analytics})


@dashboard_bp.get("/api/dashboard/financial-summary")
@dashboard_bp.get("/api/v1/dashboard/financial-summary")
@admin_required
def api_financial_summary():
    """
    Financial breakdown by period.

    Query params:
        period    : daily | weekly | monthly | quarterly | yearly (default: monthly)
        start     : YYYY-MM-DD (overrides period)
        end       : YYYY-MM-DD (overrides period)
    """
    period = request.args.get("period", "monthly")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if start_str and end_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        if period not in _VALID_PERIODS:
            return jsonify({"success": False, "error": f"Invalid period. Use: {', '.join(_VALID_PERIODS)}"}), 400
        start, end = period_range(period)

    log.info("Financial summary | admin_id=%s | start=%s | end=%s", session["user_id"], start, end)
    try:
        summary = dashboard_service.get_financial_summary(start, end)
    except Exception as exc:  # noqa: BLE001
        log.exception("Financial summary failed | error=%s", exc)
        summary = {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "total_expenses": 0,
            "approved_expenses": 0,
            "total_advances": 0,
            "approved_advances": 0,
            "pending_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "reimbursement_pending_count": 0,
            "reimbursement_pending_amount": 0,
        }
    return jsonify({"success": True, "summary": summary})


@dashboard_bp.get("/api/dashboard/attendance-summary")
@dashboard_bp.get("/api/v1/dashboard/attendance-summary")
@manager_or_admin_required
def api_attendance_summary():
    """
    Attendance analytics by period.

    Query params:
        period    : daily | weekly | monthly | quarterly | yearly (default: monthly)
        start     : YYYY-MM-DD (overrides period)
        end       : YYYY-MM-DD (overrides period)
    """
    period = request.args.get("period", "monthly")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if start_str and end_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        if period not in _VALID_PERIODS:
            return jsonify({"success": False, "error": f"Invalid period. Use: {', '.join(_VALID_PERIODS)}"}), 400
        start, end = period_range(period)

    log.info("Attendance summary | admin_id=%s | start=%s | end=%s", session["user_id"], start, end)
    try:
        summary = dashboard_service.get_attendance_summary(start, end)
    except Exception as exc:  # noqa: BLE001
        log.exception("Attendance summary failed | error=%s", exc)
        summary = {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "total_staff": 0,
            "total_days_present": 0,
            "total_minutes": 0,
            "total_duration": "0h 0m",
            "staff_summaries": [],
        }
    return jsonify({"success": True, "summary": summary})
