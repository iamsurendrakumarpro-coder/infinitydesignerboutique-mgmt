"""
modules/settings/routes.py - Settings Management Blueprint.

API Routes
----------
GET   /api/settings/<config_type>   - Get settings for a config type
PATCH /api/settings/<config_type>   - Update settings (admin only)
GET   /api/settings                 - Get all settings
"""
from __future__ import annotations

from flask import Blueprint, request, session, jsonify

from middleware.auth_middleware import login_required, admin_required
from services import settings_service
from utils.logger import get_logger

log = get_logger(__name__)

settings_bp = Blueprint("settings", __name__)

VALID_CONFIG_TYPES = ["app_config", "designations", "staff_statuses", "salary_config"]


@settings_bp.get("/api/settings")
@settings_bp.get("/api/v1/settings")
@login_required
def api_get_all_settings():
    """Get all settings for all config types."""
    log.info("Get all settings | user_id=%s", session["user_id"])
    all_settings = settings_service.get_all_settings()
    return jsonify({"success": True, "settings": all_settings})


@settings_bp.get("/api/settings/<config_type>")
@settings_bp.get("/api/v1/settings/<config_type>")
@login_required
def api_get_settings(config_type: str):
    """Get settings for a specific config type."""
    if config_type not in VALID_CONFIG_TYPES:
        return jsonify({"success": False, "error": f"Invalid config type: {config_type}"}), 400

    log.info("Get settings | config_type=%s | user_id=%s", config_type, session["user_id"])
    settings = settings_service.get_settings(config_type)
    return jsonify({"success": True, "settings": settings})


@settings_bp.patch("/api/settings/<config_type>")
@settings_bp.patch("/api/v1/settings/<config_type>")
@admin_required
def api_update_settings(config_type: str):
    """Admin update settings for a config type."""
    if config_type not in VALID_CONFIG_TYPES:
        return jsonify({"success": False, "error": f"Invalid config type: {config_type}"}), 400

    admin_id = session["user_id"]
    data = request.get_json() or {}

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    log.info("Update settings | config_type=%s | admin_id=%s | fields=%s",
             config_type, admin_id, list(data.keys()))

    success, error = settings_service.update_settings(config_type, data, admin_id)
    if not success:
        log.error("Update settings failed | config_type=%s | error=%s", config_type, error)
        return jsonify({"success": False, "error": error}), 400

    # Return updated settings
    updated = settings_service.get_settings(config_type, use_cache=False)
    return jsonify({"success": True, "settings": updated})


@settings_bp.post("/api/settings/<config_type>/invalidate-cache")
@settings_bp.post("/api/v1/settings/<config_type>/invalidate-cache")
@admin_required
def api_invalidate_cache(config_type: str):
    """Admin invalidate settings cache for a config type."""
    if config_type not in VALID_CONFIG_TYPES and config_type != "all":
        return jsonify({"success": False, "error": f"Invalid config type: {config_type}"}), 400

    admin_id = session["user_id"]
    log.info("Invalidate cache | config_type=%s | admin_id=%s", config_type, admin_id)

    if config_type == "all":
        settings_service.invalidate_cache()
    else:
        settings_service.invalidate_cache(config_type)

    return jsonify({"success": True})


# -- Designation-specific convenience endpoints --------------------------------


@settings_bp.post("/api/settings/designations/add")
@settings_bp.post("/api/v1/settings/designations/add")
@admin_required
def api_add_designation():
    """Admin add a new designation."""
    admin_id = session["user_id"]
    data = request.get_json() or {}

    key = data.get("key", "").strip().lower().replace(" ", "_")
    label = data.get("label", "").strip()

    if not key or not label:
        return jsonify({"success": False, "error": "Both key and label are required"}), 400

    # Get current designations
    current = settings_service.get_settings("designations")
    designation_list = current.get("list", [])
    labels = current.get("labels", {})

    if key in designation_list:
        return jsonify({"success": False, "error": f"Designation '{key}' already exists"}), 400

    # Add new designation
    designation_list.append(key)
    labels[key] = label

    success, error = settings_service.update_settings(
        "designations",
        {"list": designation_list, "labels": labels},
        admin_id
    )

    if not success:
        return jsonify({"success": False, "error": error}), 400

    log.info("Designation added | key=%s | label=%s | admin_id=%s", key, label, admin_id)
    return jsonify({"success": True, "designation": {"key": key, "label": label}})


@settings_bp.delete("/api/settings/designations/<key>")
@settings_bp.delete("/api/v1/settings/designations/<key>")
@admin_required
def api_remove_designation(key: str):
    """Admin remove a designation."""
    admin_id = session["user_id"]

    # Get current designations
    current = settings_service.get_settings("designations")
    designation_list = current.get("list", [])
    labels = current.get("labels", {})

    if key not in designation_list:
        return jsonify({"success": False, "error": f"Designation '{key}' not found"}), 404

    # Remove designation
    designation_list.remove(key)
    labels.pop(key, None)

    success, error = settings_service.update_settings(
        "designations",
        {"list": designation_list, "labels": labels},
        admin_id
    )

    if not success:
        return jsonify({"success": False, "error": error}), 400

    log.info("Designation removed | key=%s | admin_id=%s", key, admin_id)
    return jsonify({"success": True})


@settings_bp.get("/api/settings/designations/<key>/staff-count")
@settings_bp.get("/api/v1/settings/designations/<key>/staff-count")
@admin_required
def api_designation_staff_count(key: str):
    """Return the number of active/inactive staff with this designation."""
    from utils.db.postgres_client import get_postgres_connection
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM staff WHERE designation = %s AND status != 'deactivated'",
                (key,)
            )
            row = cur.fetchone()
            count = int(row[0]) if row else 0
    finally:
        conn.close()
    return jsonify({"success": True, "count": count})


@settings_bp.patch("/api/settings/designations/<key>")
@settings_bp.patch("/api/v1/settings/designations/<key>")
@admin_required
def api_update_designation(key: str):
    """Admin update a designation label."""
    admin_id = session["user_id"]
    data = request.get_json() or {}

    new_label = data.get("label", "").strip()
    if not new_label:
        return jsonify({"success": False, "error": "Label is required"}), 400

    # Get current designations
    current = settings_service.get_settings("designations")
    designation_list = current.get("list", [])
    labels = current.get("labels", {})

    if key not in designation_list:
        return jsonify({"success": False, "error": f"Designation '{key}' not found"}), 404

    # Update label
    labels[key] = new_label

    success, error = settings_service.update_settings(
        "designations",
        {"labels": labels},
        admin_id
    )

    if not success:
        return jsonify({"success": False, "error": error}), 400

    log.info("Designation updated | key=%s | label=%s | admin_id=%s", key, new_label, admin_id)
    return jsonify({"success": True, "designation": {"key": key, "label": new_label}})
