"""
modules/users/routes.py – User Management Blueprint (JSON API only).

API Routes
----------
GET    /api/users/staff                    – List all staff
POST   /api/users/staff                    – Create staff
GET    /api/users/staff/<uid>              – Get staff profile
PUT    /api/users/staff/<uid>              – Update staff
PATCH  /api/users/staff/<uid>/status       – Change status
POST   /api/users/staff/<uid>/reset-pin    – Admin resets staff PIN
POST   /api/users/staff/<uid>/skills       – Add skill
DELETE /api/users/staff/<uid>/skills       – Remove skill
GET    /api/users/staff/<uid>/gallery      – List gallery
POST   /api/users/staff/<uid>/gallery      – Upload image
DELETE /api/users/staff/<uid>/gallery/<gid>– Delete gallery image
GET    /api/users/staff/<uid>/performance  – List perf logs
POST   /api/users/staff/<uid>/performance  – Add perf log
DELETE /api/users/staff/<uid>/performance/<lid> – Delete log
GET    /api/users/admins                   – List admins
POST   /api/users/admins                   – Create admin
"""
from __future__ import annotations

from flask import (
    Blueprint,
    request,
    session,
    jsonify,
)

from middleware.auth_middleware import admin_required, login_required
from services import user_service, auth_service
from utils.validators import (
    validate_staff_create,
    validate_staff_update,
    validate_admin_create,
    validate_pin,
)
from utils.logger import get_logger, audit_log

log = get_logger(__name__)

users_bp = Blueprint("users", __name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Staff API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@users_bp.get("/api/users/staff")
@admin_required
def api_list_staff():
    status_filter = request.args.get("status")
    log.info("Listing staff | admin_id=%s | status_filter=%s", session["user_id"], status_filter)
    staff = user_service.list_staff(status_filter=status_filter)
    log.info("Listed staff | count=%d", len(staff))
    return jsonify({"success": True, "staff": staff})


@users_bp.post("/api/users/staff")
@admin_required
def api_create_staff():
    data = request.get_json(silent=True) or {}
    log.info("Creating staff | admin_id=%s", session["user_id"])
    errors = validate_staff_create(data)
    if errors:
        log.warning("Staff creation validation failed | admin_id=%s | errors=%s", session["user_id"], errors)
        return jsonify({"success": False, "errors": errors}), 400

    success, error, doc = user_service.create_staff(data, created_by=session["user_id"])
    if not success:
        log.warning("Staff creation conflict | admin_id=%s | error=%s", session["user_id"], error)
        return jsonify({"success": False, "error": error}), 409

    log.info("Staff created via API | created_by=%s | user_id=%s", session["user_id"], doc.get("user_id"))
    audit_log(session["user_id"], "CREATE_STAFF", "staff/%s" % doc.get("user_id"))
    return jsonify({"success": True, "staff": doc}), 201


@users_bp.get("/api/users/staff/<uid>")
@login_required
def api_get_staff(uid: str):
    log.info("Fetching staff profile | admin_id=%s | staff_id=%s", session["user_id"], uid)
    staff = user_service.get_staff(uid)
    if not staff:
        log.warning("Staff not found | staff_id=%s", uid)
        return jsonify({"success": False, "error": "Staff member not found."}), 404
    log.info("Staff profile retrieved | staff_id=%s", uid)
    return jsonify({"success": True, "staff": staff})


@users_bp.put("/api/users/staff/<uid>")
@admin_required
def api_update_staff(uid: str):
    data = request.get_json(silent=True) or {}
    log.info("Updating staff | admin_id=%s | staff_id=%s", session["user_id"], uid)
    errors = validate_staff_update(data)
    if errors:
        log.warning("Staff update validation failed | staff_id=%s | errors=%s", uid, errors)
        return jsonify({"success": False, "errors": errors}), 400

    success, error = user_service.update_staff(uid, data, updated_by=session["user_id"])
    if not success:
        log.warning("Staff update failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 404

    log.info("Staff updated | admin_id=%s | staff_id=%s", session["user_id"], uid)
    audit_log(session["user_id"], "UPDATE_STAFF", "staff/%s" % uid)
    return jsonify({"success": True})


@users_bp.patch("/api/users/staff/<uid>/status")
@admin_required
def api_staff_status(uid: str):
    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip()
    log.info("Changing staff status | admin_id=%s | staff_id=%s | new_status=%s", session["user_id"], uid, new_status)
    success, error = user_service.set_staff_status(uid, new_status, session["user_id"])
    if not success:
        log.warning("Staff status change failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 400
    log.info("Staff status changed | staff_id=%s | new_status=%s", uid, new_status)
    audit_log(session["user_id"], "CHANGE_STAFF_STATUS", "staff/%s" % uid, detail="new_status=%s" % new_status)
    return jsonify({"success": True})


@users_bp.post("/api/users/staff/<uid>/reset-pin")
@admin_required
def api_reset_staff_pin(uid: str):
    log.info("Resetting staff PIN | admin_id=%s | staff_id=%s", session["user_id"], uid)
    data = request.get_json(silent=True) or {}
    temp_pin = str(data.get("temp_pin", "")).strip()
    ok, err = validate_pin(temp_pin)
    if not ok:
        log.warning("PIN reset validation failed | staff_id=%s | error=%s", uid, err)
        return jsonify({"success": False, "error": err}), 400

    success, error = auth_service.admin_reset_staff_pin(session["user_id"], uid, temp_pin)
    if not success:
        log.warning("PIN reset failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 404
    log.info("Staff PIN reset | admin_id=%s | staff_id=%s", session["user_id"], uid)
    audit_log(session["user_id"], "RESET_STAFF_PIN", "staff/%s" % uid)
    return jsonify({"success": True})


# ── Skills ────────────────────────────────────────────────────────────────────

@users_bp.post("/api/users/staff/<uid>/skills")
@admin_required
def api_add_skill(uid: str):
    data = request.get_json(silent=True) or {}
    skill = str(data.get("skill", "")).strip()
    log.info("Adding skill | admin_id=%s | staff_id=%s | skill=%s", session["user_id"], uid, skill)
    success, error = user_service.add_skill(uid, skill, session["user_id"])
    if not success:
        log.warning("Add skill failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 400
    log.info("Skill added | staff_id=%s | skill=%s", uid, skill)
    return jsonify({"success": True})


@users_bp.delete("/api/users/staff/<uid>/skills")
@admin_required
def api_remove_skill(uid: str):
    data = request.get_json(silent=True) or {}
    skill = str(data.get("skill", "")).strip()
    log.info("Removing skill | admin_id=%s | staff_id=%s | skill=%s", session["user_id"], uid, skill)
    success, error = user_service.remove_skill(uid, skill, session["user_id"])
    if not success:
        log.warning("Remove skill failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 400
    log.info("Skill removed | staff_id=%s | skill=%s", uid, skill)
    return jsonify({"success": True})


# ── Gallery ───────────────────────────────────────────────────────────────────

@users_bp.get("/api/users/staff/<uid>/gallery")
@admin_required
def api_list_gallery(uid: str):
    log.info("Listing gallery | admin_id=%s | staff_id=%s", session["user_id"], uid)
    items = user_service.list_gallery(uid)
    log.info("Gallery listed | staff_id=%s | count=%d", uid, len(items))
    return jsonify({"success": True, "gallery": items})


@users_bp.post("/api/users/staff/<uid>/gallery")
@admin_required
def api_upload_gallery(uid: str):
    log.info("Uploading gallery image | admin_id=%s | staff_id=%s", session["user_id"], uid)
    if "image" not in request.files:
        log.warning("Gallery upload missing image file | staff_id=%s", uid)
        return jsonify({"success": False, "error": "No image file provided."}), 400

    file = request.files["image"]
    if not file.filename:
        log.warning("Gallery upload missing filename | staff_id=%s", uid)
        return jsonify({"success": False, "error": "No filename provided."}), 400

    caption = request.form.get("caption", "")
    file_bytes = file.read()

    if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        log.warning("Gallery upload exceeds size limit | staff_id=%s | size=%d", uid, len(file_bytes))
        return jsonify({"success": False, "error": "Image must be smaller than 10 MB."}), 400

    success, error, item = user_service.upload_gallery_image(
        uid, file_bytes, file.filename, caption, uploaded_by=session["user_id"]
    )
    if not success:
        log.error("Gallery upload failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 500
    log.info("Gallery image uploaded | staff_id=%s | filename=%s", uid, file.filename)
    return jsonify({"success": True, "item": item}), 201


@users_bp.delete("/api/users/staff/<uid>/gallery/<gid>")
@admin_required
def api_delete_gallery(uid: str, gid: str):
    log.info("Deleting gallery image | admin_id=%s | staff_id=%s | gallery_id=%s", session["user_id"], uid, gid)
    success, error = user_service.delete_gallery_image(uid, gid, session["user_id"])
    if not success:
        log.warning("Gallery image delete failed | staff_id=%s | gallery_id=%s | error=%s", uid, gid, error)
        return jsonify({"success": False, "error": error}), 404
    log.info("Gallery image deleted | staff_id=%s | gallery_id=%s", uid, gid)
    return jsonify({"success": True})


# ── Performance Logs ──────────────────────────────────────────────────────────

@users_bp.get("/api/users/staff/<uid>/performance")
@admin_required
def api_list_perf_logs(uid: str):
    log.info("Listing performance logs | admin_id=%s | staff_id=%s", session["user_id"], uid)
    logs = user_service.list_performance_logs(uid)
    log.info("Performance logs listed | staff_id=%s | count=%d", uid, len(logs))
    return jsonify({"success": True, "logs": logs})


@users_bp.post("/api/users/staff/<uid>/performance")
@admin_required
def api_add_perf_log(uid: str):
    data = request.get_json(silent=True) or {}
    note = str(data.get("note", "")).strip()
    log.info("Adding performance log | admin_id=%s | staff_id=%s", session["user_id"], uid)
    if not note:
        log.warning("Performance log empty note | staff_id=%s", uid)
        return jsonify({"success": False, "error": "Note cannot be empty."}), 400

    success, error, log_doc = user_service.add_performance_log(uid, note, session["user_id"])
    if not success:
        log.warning("Add performance log failed | staff_id=%s | error=%s", uid, error)
        return jsonify({"success": False, "error": error}), 400
    log.info("Performance log added | staff_id=%s", uid)
    return jsonify({"success": True, "log": log_doc}), 201


@users_bp.delete("/api/users/staff/<uid>/performance/<lid>")
@admin_required
def api_delete_perf_log(uid: str, lid: str):
    log.info("Deleting performance log | admin_id=%s | staff_id=%s | log_id=%s", session["user_id"], uid, lid)
    success, error = user_service.delete_performance_log(uid, lid, session["user_id"])
    if not success:
        log.warning("Delete performance log failed | staff_id=%s | log_id=%s | error=%s", uid, lid, error)
        return jsonify({"success": False, "error": error}), 404
    log.info("Performance log deleted | staff_id=%s | log_id=%s", uid, lid)
    return jsonify({"success": True})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Admin API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@users_bp.get("/api/users/admins")
@admin_required
def api_list_admins():
    log.info("Listing admins | admin_id=%s", session["user_id"])
    admins = user_service.list_admins(exclude_root=True)
    log.info("Admins listed | count=%d", len(admins))
    return jsonify({"success": True, "admins": admins})


@users_bp.post("/api/users/admins")
@admin_required
def api_create_admin():
    data = request.get_json(silent=True) or {}
    log.info("Creating admin | admin_id=%s", session["user_id"])
    errors = validate_admin_create(data)
    if errors:
        log.warning("Admin creation validation failed | admin_id=%s | errors=%s", session["user_id"], errors)
        return jsonify({"success": False, "errors": errors}), 400

    success, error, doc = user_service.create_admin(data, created_by=session["user_id"])
    if not success:
        log.warning("Admin creation conflict | admin_id=%s | error=%s", session["user_id"], error)
        return jsonify({"success": False, "error": error}), 409

    log.info("Admin created via API | created_by=%s | user_id=%s", session["user_id"], doc.get("user_id"))
    audit_log(session["user_id"], "CREATE_ADMIN", "admin/%s" % doc.get("user_id"))
    return jsonify({"success": True, "admin": doc}), 201
