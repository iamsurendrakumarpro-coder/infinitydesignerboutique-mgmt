"""
modules/financial/routes.py – Financial Requests Blueprint.

API Routes
----------
POST  /api/financial/requests       – Create financial request
GET   /api/financial/requests       – List requests (filterable)
GET   /api/financial/requests/<id>  – Get request detail
PATCH /api/financial/requests/<id>  – Admin approve/reject
"""
from __future__ import annotations

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import login_required, admin_required
from services import financial_service
from utils.logger import get_logger

log = get_logger(__name__)

financial_bp = Blueprint("financial", __name__)


@financial_bp.post("/api/financial/requests")
@login_required
def api_create_request():
    """Create a financial request (shop_expense or personal_advance)."""
    body = request.get_json(silent=True) or {}
    user_id = session["user_id"]

    log.info("Create financial request | user_id=%s | type=%s", user_id, body.get("type"))

    success, error, doc = financial_service.create_request(user_id, body)
    if not success:
        log.error("Create financial request failed | user_id=%s | error=%s", user_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "request": doc}), 201


@financial_bp.get("/api/financial/requests")
@login_required
def api_list_requests():
    """
    List financial requests.

    Query params:
        status  : pending | approved | rejected
        user_id : Filter by user (admin only; staff sees own only)
    """
    role = session.get("role")
    filters = {}

    status_filter = request.args.get("status")
    if status_filter:
        filters["status"] = status_filter

    if role == "admin":
        uid = request.args.get("user_id")
        if uid:
            filters["user_id"] = uid
    else:
        filters["user_id"] = session["user_id"]

    log.info("List financial requests | role=%s | filters=%s", role, filters)
    requests_list = financial_service.get_requests(filters)
    return jsonify({"success": True, "requests": requests_list})


@financial_bp.get("/api/financial/requests/<request_id>")
@login_required
def api_get_request(request_id: str):
    """Get a single financial request."""
    log.info("Get financial request | request_id=%s", request_id)
    doc = financial_service.get_request(request_id)
    if not doc:
        return jsonify({"success": False, "error": "Request not found."}), 404

    role = session.get("role")
    if role != "admin" and doc.get("user_id") != session["user_id"]:
        return jsonify({"success": False, "error": "Access denied."}), 403

    return jsonify({"success": True, "request": doc})


@financial_bp.patch("/api/financial/requests/<request_id>")
@admin_required
def api_review_request(request_id: str):
    """Admin approve or reject a financial request."""
    body = request.get_json(silent=True) or {}
    action = str(body.get("action", "")).strip().lower()
    notes = str(body.get("notes", "")).strip()
    admin_id = session["user_id"]

    if action not in ("approve", "reject"):
        return jsonify({"success": False, "error": "Action must be 'approve' or 'reject'."}), 400

    log.info("Review financial request | request_id=%s | action=%s | admin_id=%s",
             request_id, action, admin_id)

    if action == "approve":
        success, error = financial_service.approve_request(request_id, admin_id, notes)
    else:
        success, error = financial_service.reject_request(request_id, admin_id, notes)

    if not success:
        log.error("Review financial request failed | request_id=%s | error=%s", request_id, error)
        return jsonify({"success": False, "error": error}), 400

    return jsonify({"success": True, "action": action})
