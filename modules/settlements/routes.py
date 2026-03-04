"""
modules/settlements/routes.py – Settlement Management Blueprint.

API Routes
----------
POST /api/settlements/generate       – Generate weekly settlements
GET  /api/settlements                – List settlements (filterable)
GET  /api/settlements/<id>           – Get settlement detail
GET  /api/settlements/user/<user_id> – Get settlements for a user
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import login_required, admin_required
from services import settlement_service
from utils.logger import get_logger

log = get_logger(__name__)

settlements_bp = Blueprint("settlements", __name__)


@settlements_bp.post("/api/settlements/generate")
@admin_required
def api_generate_settlements():
    """Generate weekly settlements for all active staff."""
    body = request.get_json(silent=True) or {}
    admin_id = session["user_id"]

    week_start_str = str(body.get("week_start", "")).strip()
    week_end_str = str(body.get("week_end", "")).strip()

    if not week_start_str or not week_end_str:
        return jsonify({"success": False, "error": "week_start and week_end are required (YYYY-MM-DD)."}), 400

    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        week_end = datetime.strptime(week_end_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400

    if week_start > week_end:
        return jsonify({"success": False, "error": "week_start must be before or equal to week_end."}), 400

    log.info("Generate settlements | admin_id=%s | period=%s to %s", admin_id, week_start, week_end)

    success, error, settlements = settlement_service.generate_weekly_settlement(
        week_start, week_end, generated_by=admin_id
    )
    if not success:
        log.error("Generate settlements failed | error=%s", error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "settlements": settlements, "count": len(settlements)}), 201


@settlements_bp.get("/api/settlements")
@admin_required
def api_list_settlements():
    """
    List settlements with optional filters.

    Query params: user_id, week_start, week_end.
    """
    filters = {}
    if request.args.get("user_id"):
        filters["user_id"] = request.args["user_id"]
    if request.args.get("week_start"):
        filters["week_start"] = request.args["week_start"]
    if request.args.get("week_end"):
        filters["week_end"] = request.args["week_end"]

    log.info("List settlements | filters=%s", filters)
    settlements = settlement_service.get_settlements(filters if filters else None)
    return jsonify({"success": True, "settlements": settlements})


@settlements_bp.get("/api/settlements/<settlement_id>")
@login_required
def api_get_settlement(settlement_id: str):
    """Get a single settlement."""
    log.info("Get settlement | settlement_id=%s", settlement_id)
    doc = settlement_service.get_settlement(settlement_id)
    if not doc:
        return jsonify({"success": False, "error": "Settlement not found."}), 404

    role = session.get("role")
    if role != "admin" and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    return jsonify({"success": True, "settlement": doc})


@settlements_bp.get("/api/settlements/user/<user_id>")
@login_required
def api_user_settlements(user_id: str):
    """Get all settlements for a specific user."""
    role = session.get("role")
    if role != "admin" and session["user_id"] != user_id:
        return jsonify({"success": False, "error": "Access denied."}), 403

    log.info("Get user settlements | user_id=%s | requested_by=%s", user_id, session["user_id"])
    settlements = settlement_service.get_settlements_for_user(user_id)
    return jsonify({"success": True, "settlements": settlements})
