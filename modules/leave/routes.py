"""
modules/leave/routes.py - Leave Management Blueprint.

API Routes
----------
POST   /api/leave/requests            - Apply for leave (any logged-in user)
GET    /api/leave/requests            - List leave requests (staff: own, admin: all)
GET    /api/leave/requests/<id>       - Get single leave request
PATCH  /api/leave/requests/<id>       - Admin approve/reject
DELETE /api/leave/requests/<id>       - Staff cancel pending leave
GET    /api/leave/today               - Staff on leave today (dashboard)
GET    /api/leave/pending-count       - Pending leave count (badge)
"""
from __future__ import annotations

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import login_required, manager_or_admin_required
from services import leave_service
from utils.logger import get_logger

log = get_logger(__name__)

leave_bp = Blueprint("leave", __name__)


@leave_bp.post("/api/leave/requests")
@login_required
def api_create_leave():
    """Apply for leave."""
    body = request.get_json(silent=True) or {}
    user_id = session["user_id"]

    log.info("Create leave request | user_id=%s | type=%s", user_id, body.get("leave_type"))

    success, error, doc = leave_service.create_leave_request(user_id, body)
    if not success:
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "leave_request": doc}), 201


@leave_bp.get("/api/leave/requests")
@login_required
def api_list_leaves():
    """
    List leave requests.

    Query params:
        status  : pending | approved | rejected | cancelled
        user_id : Filter by user (admin/manager only; staff sees own only)
    """
    role = session.get("role")
    filters = {}

    status_filter = request.args.get("status")
    if status_filter:
        filters["status"] = status_filter

    if role in {"admin", "manager"}:
        uid = request.args.get("user_id")
        if uid:
            filters["user_id"] = uid
    else:
        filters["user_id"] = session["user_id"]

    leaves = leave_service.get_leave_requests(filters)
    log.info("List leave requests | role=%s | filters=%s | count=%d", role, filters, len(leaves))
    return jsonify({"success": True, "leaves": leaves})


@leave_bp.get("/api/leave/requests/<request_id>")
@login_required
def api_get_leave(request_id: str):
    """Get a single leave request."""
    doc = leave_service.get_leave_request(request_id)
    if not doc:
        return jsonify({"success": False, "error": "Leave request not found."}), 404

    # Staff can only see their own
    if session.get("role") not in {"admin", "manager"} and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    return jsonify({"success": True, "leave_request": doc})


@leave_bp.patch("/api/leave/requests/<request_id>")
@manager_or_admin_required
def api_review_leave(request_id: str):
    """Admin approve or reject a leave request."""
    body = request.get_json(silent=True) or {}
    action = body.get("action", "").strip()
    admin_notes = body.get("admin_notes", "").strip()
    admin_id = session["user_id"]

    log.info("Review leave | request_id=%s | action=%s | admin_id=%s", request_id, action, admin_id)

    success, error, doc = leave_service.review_leave(request_id, action, admin_id, admin_notes)
    if not success:
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "leave_request": doc})


@leave_bp.delete("/api/leave/requests/<request_id>")
@login_required
def api_cancel_leave(request_id: str):
    """Staff cancel their own pending leave."""
    user_id = session["user_id"]
    log.info("Cancel leave | request_id=%s | user_id=%s", request_id, user_id)

    success, error = leave_service.cancel_leave(request_id, user_id)
    if not success:
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "message": "Leave request cancelled."})


@leave_bp.get("/api/leave/today")
@manager_or_admin_required
def api_leaves_today():
    """Get staff on leave today (for dashboard)."""
    leaves = leave_service.get_leaves_for_date()
    return jsonify({"success": True, "leaves": leaves, "count": len(leaves)})


@leave_bp.get("/api/leave/pending-count")
@manager_or_admin_required
def api_pending_leave_count():
    """Get count of pending leave requests (for badge)."""
    count = leave_service.get_pending_leave_count()
    return jsonify({"success": True, "count": count})
