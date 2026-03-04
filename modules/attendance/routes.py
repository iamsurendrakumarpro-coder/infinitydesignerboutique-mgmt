"""
modules/attendance/routes.py – Attendance Blueprint (JSON API only).

API Routes
----------
GET  /api/attendance/status    – Get today's punch status for current user
POST /api/attendance/punch     – Punch in or out (staff only)
GET  /api/attendance/history   – History with date range
GET  /api/attendance/analytics – Analytics (staff: own; admin: all or by uid)
"""
from __future__ import annotations

from flask import (
    Blueprint,
    request,
    session,
    jsonify,
)

from middleware.auth_middleware import login_required
from services import attendance_service
from utils.logger import get_logger
from utils.timezone_utils import period_range, today_ist_str

log = get_logger(__name__)

attendance_bp = Blueprint("attendance", __name__)

_VALID_PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly")


# ── API routes ────────────────────────────────────────────────────────────────

@attendance_bp.get("/api/attendance/status")
@login_required
def api_status():
    """Get today's punch status for the current user (or admin-specified user)."""
    user_id = request.args.get("user_id") if session.get("role") == "admin" else session["user_id"]
    if not user_id:
        user_id = session["user_id"]

    log.info("Attendance status check | user_id=%s | requested_by=%s", user_id, session["user_id"])
    record = attendance_service.get_today_status(user_id)
    return jsonify({"success": True, "record": record})


@attendance_bp.post("/api/attendance/punch")
@login_required
def api_punch():
    """Staff-only punch in/out with double-click guard."""
    if session.get("role") != "staff":
        return jsonify({"success": False, "error": "Only staff can punch in/out."}), 403

    if session.get("is_first_login"):
        return jsonify({
            "success": False,
            "error": "Please change your PIN before punching in.",
            "first_login": True,
        }), 403

    user_id = session["user_id"]
    log.info("Punch attempt | user_id=%s", user_id)
    success, message, record = attendance_service.punch(user_id)
    status_code = 200 if success else 400
    return jsonify({"success": success, "message": message, "record": record}), status_code


@attendance_bp.get("/api/attendance/history")
@login_required
def api_history():
    """
    Get attendance history.

    Query params:
        user_id : Required for admin; ignored for staff (own data).
        start   : YYYY-MM-DD start date.
        end     : YYYY-MM-DD end date.
        period  : daily | weekly | monthly | quarterly | yearly
                  (overrides start/end if provided)
    """
    role = session.get("role")

    if role == "admin":
        uid = request.args.get("user_id")
        if not uid:
            return jsonify({"success": False, "error": "user_id is required."}), 400
    else:
        uid = session["user_id"]

    period = request.args.get("period")
    if period:
        if period not in _VALID_PERIODS:
            return jsonify({"success": False, "error": f"Invalid period. Use: {', '.join(_VALID_PERIODS)}"}), 400
        start, end = period_range(period)
    else:
        try:
            from datetime import datetime
            start_str = request.args.get("start", today_ist_str())
            end_str = request.args.get("end", today_ist_str())
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

    log.info("Attendance history | user_id=%s | start=%s | end=%s", uid, start, end)
    records = attendance_service.get_attendance_history(uid, start, end)
    return jsonify({"success": True, "records": records, "user_id": uid})


@attendance_bp.get("/api/attendance/analytics")
@login_required
def api_analytics():
    """
    Get attendance analytics.

    Query params:
        period  : daily | weekly | monthly | quarterly | yearly  (default: monthly)
        user_id : Admin only – specific staff member.  Omit for all-staff summary.
    """
    period = request.args.get("period", "monthly")
    if period not in _VALID_PERIODS:
        return jsonify({"success": False, "error": f"Invalid period. Use: {', '.join(_VALID_PERIODS)}"}), 400

    role = session.get("role")

    if role == "staff":
        log.info("Staff analytics | user_id=%s | period=%s", session["user_id"], period)
        analytics = attendance_service.get_staff_analytics(session["user_id"], period)
        return jsonify({"success": True, "analytics": analytics})

    # Admin
    uid = request.args.get("user_id")
    if uid:
        log.info("Admin analytics for user | user_id=%s | period=%s", uid, period)
        analytics = attendance_service.get_staff_analytics(uid, period)
        return jsonify({"success": True, "analytics": analytics})

    log.info("Admin all-staff analytics | period=%s", period)
    all_analytics = attendance_service.get_all_staff_analytics(period)
    return jsonify({"success": True, "analytics": all_analytics})
