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

from middleware.auth_middleware import admin_required
from services import dashboard_service
from utils.logger import get_logger
from utils.timezone_utils import period_range

log = get_logger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

_VALID_PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")


@dashboard_bp.get("/api/dashboard/summary")
@admin_required
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
    summary = dashboard_service.get_daily_summary(target_date)
    return jsonify({"success": True, "summary": summary})


@dashboard_bp.get("/api/dashboard/analytics")
@admin_required
def api_dashboard_analytics():
    """Get chart-ready analytics data for the dashboard."""
    log.info("Dashboard analytics | admin_id=%s", session["user_id"])
    analytics = dashboard_service.get_dashboard_analytics()
    return jsonify({"success": True, "analytics": analytics})


@dashboard_bp.get("/api/dashboard/financial-summary")
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
    summary = dashboard_service.get_financial_summary(start, end)
    return jsonify({"success": True, "summary": summary})


@dashboard_bp.get("/api/dashboard/attendance-summary")
@admin_required
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
    summary = dashboard_service.get_attendance_summary(start, end)
    return jsonify({"success": True, "summary": summary})
