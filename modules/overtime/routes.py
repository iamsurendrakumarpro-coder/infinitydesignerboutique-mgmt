"""
modules/overtime/routes.py - Overtime Management Blueprint.

API Routes
----------
GET   /api/overtime/pending          - List overtime pending approval
GET   /api/overtime/user/<user_id>   - Get overtime for a user
PATCH /api/overtime/<id>/approve     - Admin approve overtime
PATCH /api/overtime/<id>/reject      - Admin reject overtime
"""
from __future__ import annotations

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import login_required, admin_required
from services import overtime_service
from utils.logger import get_logger

log = get_logger(__name__)

overtime_bp = Blueprint("overtime", __name__)


@overtime_bp.get("/api/overtime/pending")
@admin_required
def api_pending_overtime():
    """List all overtime records pending approval."""
    log.info("List pending overtime | admin_id=%s", session["user_id"])
    records = overtime_service.get_pending_overtime()
    return jsonify({"success": True, "records": records})


@overtime_bp.get("/api/overtime/user/<user_id>")
@login_required
def api_user_overtime(user_id: str):
    """Get overtime records for a specific user."""
    role = session.get("role")
    if role != "admin" and session["user_id"] != user_id:
        return jsonify({"success": False, "error": "Access denied."}), 403

    log.info("Get user overtime | user_id=%s | requested_by=%s", user_id, session["user_id"])
    records = overtime_service.get_overtime_for_user(user_id)
    return jsonify({"success": True, "records": records})


@overtime_bp.patch("/api/overtime/<overtime_id>/approve")
@admin_required
def api_approve_overtime(overtime_id: str):
    """Admin approve an overtime record."""
    admin_id = session["user_id"]
    log.info("Approve overtime | overtime_id=%s | admin_id=%s", overtime_id, admin_id)

    success, error = overtime_service.approve_overtime(overtime_id, admin_id)
    if not success:
        log.error("Approve overtime failed | overtime_id=%s | error=%s", overtime_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True})


@overtime_bp.patch("/api/overtime/<overtime_id>/reject")
@admin_required
def api_reject_overtime(overtime_id: str):
    """Admin reject an overtime record."""
    admin_id = session["user_id"]
    log.info("Reject overtime | overtime_id=%s | admin_id=%s", overtime_id, admin_id)

    success, error = overtime_service.reject_overtime(overtime_id, admin_id)
    if not success:
        log.error("Reject overtime failed | overtime_id=%s | error=%s", overtime_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True})
