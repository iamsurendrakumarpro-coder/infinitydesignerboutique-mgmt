"""
services/user_service.py – User management business logic.

Handles creation, retrieval, updates, status changes, gallery management,
and performance-log management for both admins and staff.

Firestore structure
-------------------
admins/{user_id}            – Admin profile documents
staff/{user_id}             – Staff profile documents
staff/{user_id}/work_gallery/{image_id}      – Gallery images
staff/{user_id}/performance_logs/{log_id}    – Performance notes
phone_index/{phone_number}  – Unique-phone lookup (for uniqueness check)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from services.auth_service import hash_pin
from utils.firebase_client import get_firestore, get_storage_bucket
from utils.logger import get_logger, audit_log
from utils.timezone_utils import now_utc, today_ist_str
from config import get_config

log = get_logger(__name__)
cfg = get_config()

# ── Collection constants ──────────────────────────────────────────────────────
_ADMINS = "admins"
_STAFF = "staff"
_PHONE_INDEX = "phone_index"


def compute_daily_salary(weekly_salary: float) -> float:
    """Compute daily salary from weekly salary using config WORKING_DAYS_PER_WEEK."""
    return round(weekly_salary / cfg.WORKING_DAYS_PER_WEEK, 2)


# ── Phone uniqueness ──────────────────────────────────────────────────────────

def is_phone_taken(phone: str) -> bool:
    """Return True if the phone number is already registered (in either collection)."""
    db = get_firestore()
    phone = str(phone).strip()

    # Check admins
    admins = list(db.collection(_ADMINS).where("phone_number", "==", phone).limit(1).stream())
    if admins:
        return True

    # Check staff
    staff = list(db.collection(_STAFF).where("phone_number", "==", phone).limit(1).stream())
    return bool(staff)


# ── Admin CRUD ────────────────────────────────────────────────────────────────

def create_admin(data: dict, created_by: str | None = None) -> tuple[bool, str, dict]:
    """
    Create a new admin user.

    Parameters
    ----------
    data        : Must contain: full_name, phone_number, temp_pin (optional).
    created_by  : user_id of the creating admin; None for root seeding.

    Returns (success, error_message, created_doc_dict).
    """
    db = get_firestore()
    phone = str(data["phone_number"]).strip()

    if is_phone_taken(phone):
        log.warning("create_admin: phone already in use | phone=%s", phone)
        return False, "This phone number is already registered.", {}

    user_id = str(uuid.uuid4())
    plain_pin = str(data.get("temp_pin", "0000")).strip()
    pin_hash = hash_pin(plain_pin)

    doc = {
        "user_id": user_id,
        "full_name": str(data["full_name"]).strip(),
        "phone_number": phone,
        "pin_hash": pin_hash,
        "role": "admin",
        "is_root": bool(data.get("is_root", False)),
        "is_first_login": True,
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
        "created_by": created_by or "system",
    }

    db.collection(_ADMINS).document(user_id).set(doc)
    log.info(
        "Admin created | user_id=%s | phone=%s | is_root=%s | by=%s",
        user_id, phone, doc["is_root"], created_by,
    )
    audit_log(created_by or "system", "CREATE_ADMIN", f"admins/{user_id}", f"phone={phone}")
    # Omit pin_hash from returned dict
    doc.pop("pin_hash", None)
    return True, "", doc


def get_admin(user_id: str) -> dict | None:
    """Return admin data (without pin_hash) or None if not found."""
    db = get_firestore()
    doc = db.collection(_ADMINS).document(user_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data.pop("pin_hash", None)
    return data


def list_admins(exclude_root: bool = True) -> list[dict]:
    """
    Return all admin profiles (excluding pin_hash).
    If exclude_root=True, root admin(s) are omitted.
    """
    db = get_firestore()
    query = db.collection(_ADMINS)
    if exclude_root:
        query = query.where("is_root", "==", False)
    docs = query.stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        data.pop("pin_hash", None)
        result.append(data)
    log.debug("list_admins | count=%d | exclude_root=%s", len(result), exclude_root)
    return result


# ── Staff CRUD ────────────────────────────────────────────────────────────────

def create_staff(data: dict, created_by: str) -> tuple[bool, str, dict]:
    """
    Create a new staff member.

    Required keys in data::

        full_name, phone_number, designation, joining_date,
        standard_login_time, standard_logout_time,
        emergency_contact (optional), weekly_salary, temp_pin

    Returns (success, error_message, created_doc_dict).
    """
    db = get_firestore()
    phone = str(data["phone_number"]).strip()

    if is_phone_taken(phone):
        log.warning("create_staff: phone already in use | phone=%s", phone)
        return False, "This phone number is already registered.", {}

    user_id = str(uuid.uuid4())
    plain_pin = str(data.get("temp_pin", "0000")).strip()
    pin_hash = hash_pin(plain_pin)

    joining_date = str(data.get("joining_date") or today_ist_str()).strip()

    doc = {
        "user_id": user_id,
        "full_name": str(data["full_name"]).strip(),
        "phone_number": phone,
        "designation": str(data["designation"]).strip(),
        "joining_date": joining_date,
        "standard_login_time": str(data.get("standard_login_time", cfg.DEFAULT_LOGIN_TIME)).strip(),
        "standard_logout_time": str(data.get("standard_logout_time", cfg.DEFAULT_LOGOUT_TIME)).strip(),
        "emergency_contact": str(data.get("emergency_contact", "")).strip(),
        "weekly_salary": float(data["weekly_salary"]),
        "daily_salary": compute_daily_salary(float(data["weekly_salary"])),
        "skills": [],
        "status": "active",
        "pin_hash": pin_hash,
        "role": "staff",
        "is_first_login": True,
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
        "created_by": created_by,
    }

    db.collection(_STAFF).document(user_id).set(doc)
    log.info(
        "Staff created | user_id=%s | phone=%s | designation=%s | by=%s",
        user_id, phone, doc["designation"], created_by,
    )
    audit_log(created_by, "CREATE_STAFF", f"staff/{user_id}", f"phone={phone}")
    doc.pop("pin_hash", None)
    return True, "", doc


def get_staff(user_id: str) -> dict | None:
    """Return staff data (without pin_hash) or None if not found."""
    db = get_firestore()
    doc = db.collection(_STAFF).document(user_id).get()
    if not doc.exists:
        log.warning("get_staff: not found | user_id=%s", user_id)
        return None
    data = doc.to_dict()
    data.pop("pin_hash", None)
    return data


def list_staff(status_filter: str | None = None) -> list[dict]:
    """
    Return all staff profiles.

    Parameters
    ----------
    status_filter : If provided, only return staff with this status.
    """
    db = get_firestore()
    query = db.collection(_STAFF)
    if status_filter:
        query = query.where("status", "==", status_filter)
    docs = query.stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        data.pop("pin_hash", None)
        result.append(data)
    log.debug("list_staff | count=%d | filter=%s", len(result), status_filter)
    return result


def update_staff(user_id: str, data: dict, updated_by: str) -> tuple[bool, str]:
    """
    Update staff profile fields (phone is immutable).

    Returns (success, error_message).
    """
    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    doc = ref.get()
    if not doc.exists:
        return False, "Staff member not found."

    # Prevent phone number change
    data.pop("phone_number", None)
    data.pop("pin_hash", None)
    data.pop("user_id", None)
    data.pop("role", None)
    data.pop("created_at", None)
    data.pop("is_root", None)

    # Handle skills – ensure list
    if "skills" in data and isinstance(data["skills"], str):
        data["skills"] = [s.strip() for s in data["skills"].split(",") if s.strip()]

    # Numeric coercion
    if "weekly_salary" in data:
        data["weekly_salary"] = float(data["weekly_salary"])
        data["daily_salary"] = compute_daily_salary(data["weekly_salary"])

    data["updated_at"] = SERVER_TIMESTAMP

    ref.update(data)
    log.info("Staff updated | user_id=%s | by=%s | fields=%s", user_id, updated_by, list(data.keys()))
    audit_log(updated_by, "UPDATE_STAFF", f"staff/{user_id}")
    return True, ""


def set_staff_status(user_id: str, new_status: str, changed_by: str) -> tuple[bool, str]:
    """
    Set staff status to 'active', 'inactive', or 'deactivated'.
    Returns (success, error_message).
    """
    allowed = cfg.STAFF_STATUSES
    if new_status not in allowed:
        return False, f"Status must be one of: {', '.join(allowed)}."

    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    if not ref.get().exists:
        return False, "Staff member not found."

    ref.update({"status": new_status, "updated_at": SERVER_TIMESTAMP})
    log.info("Staff status changed | user_id=%s | status=%s | by=%s", user_id, new_status, changed_by)
    audit_log(changed_by, "STATUS_CHANGE", f"staff/{user_id}", f"new_status={new_status}")
    return True, ""


# ── Skills ────────────────────────────────────────────────────────────────────

def add_skill(user_id: str, skill: str, added_by: str) -> tuple[bool, str]:
    """Append a skill tag to a staff member's profile."""
    from google.cloud.firestore_v1 import ArrayUnion
    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    if not ref.get().exists:
        return False, "Staff member not found."
    skill = str(skill).strip()
    if not skill:
        return False, "Skill cannot be empty."
    ref.update({"skills": ArrayUnion([skill]), "updated_at": SERVER_TIMESTAMP})
    log.info("Skill added | user_id=%s | skill=%s | by=%s", user_id, skill, added_by)
    return True, ""


def remove_skill(user_id: str, skill: str, removed_by: str) -> tuple[bool, str]:
    """Remove a skill tag from a staff member's profile."""
    from google.cloud.firestore_v1 import ArrayRemove
    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    if not ref.get().exists:
        return False, "Staff member not found."
    ref.update({"skills": ArrayRemove([skill]), "updated_at": SERVER_TIMESTAMP})
    log.info("Skill removed | user_id=%s | skill=%s | by=%s", user_id, skill, removed_by)
    return True, ""


# ── Work Gallery ──────────────────────────────────────────────────────────────

def upload_gallery_image(user_id: str, file_bytes: bytes, filename: str, caption: str, uploaded_by: str) -> tuple[bool, str, dict]:
    """
    Upload an image to Firebase Storage and record metadata in Firestore.

    Returns (success, error_message, gallery_item_dict).
    """
    db = get_firestore()
    image_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    storage_path = f"gallery/{user_id}/{image_id}.{ext}"

    try:
        bucket = get_storage_bucket()
        blob = bucket.blob(storage_path)
        content_type = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp") else "application/octet-stream"
        if ext == "jpg":
            content_type = "image/jpeg"
        blob.upload_from_string(file_bytes, content_type=content_type)
        blob.make_public()
        image_url = blob.public_url
        log.info("Gallery image uploaded | user_id=%s | image_id=%s | url=%s", user_id, image_id, image_url)
    except Exception as exc:  # noqa: BLE001
        log.error("Gallery upload failed | user_id=%s | error=%s", user_id, exc)
        return False, f"Image upload failed: {exc}", {}

    gallery_doc = {
        "image_id": image_id,
        "image_url": image_url,
        "storage_path": storage_path,
        "caption": str(caption).strip(),
        "uploaded_at": SERVER_TIMESTAMP,
        "uploaded_by": uploaded_by,
    }

    db.collection(_STAFF).document(user_id).collection("work_gallery").document(image_id).set(gallery_doc)
    audit_log(uploaded_by, "GALLERY_UPLOAD", f"staff/{user_id}/work_gallery/{image_id}")
    return True, "", gallery_doc


def list_gallery(user_id: str) -> list[dict]:
    """Return all gallery images for a staff member."""
    db = get_firestore()
    docs = (
        db.collection(_STAFF).document(user_id)
        .collection("work_gallery")
        .order_by("uploaded_at", direction="DESCENDING")
        .stream()
    )
    return [d.to_dict() for d in docs]


def delete_gallery_image(user_id: str, image_id: str, deleted_by: str) -> tuple[bool, str]:
    """Delete a gallery image from both Storage and Firestore."""
    db = get_firestore()
    ref = (
        db.collection(_STAFF).document(user_id)
        .collection("work_gallery").document(image_id)
    )
    doc = ref.get()
    if not doc.exists:
        return False, "Gallery item not found."

    data = doc.to_dict()
    storage_path = data.get("storage_path", "")

    # Delete from Storage
    if storage_path:
        try:
            bucket = get_storage_bucket()
            blob = bucket.blob(storage_path)
            blob.delete()
            log.info("Gallery image deleted from storage | path=%s", storage_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not delete storage blob | path=%s | error=%s", storage_path, exc)

    ref.delete()
    audit_log(deleted_by, "GALLERY_DELETE", f"staff/{user_id}/work_gallery/{image_id}")
    return True, ""


# ── Performance Logs ──────────────────────────────────────────────────────────

def add_performance_log(user_id: str, note: str, created_by: str) -> tuple[bool, str, dict]:
    """Add a performance note to a staff member's profile."""
    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    if not ref.get().exists:
        return False, "Staff member not found.", {}

    if not note or not str(note).strip():
        return False, "Note cannot be empty.", {}

    log_id = str(uuid.uuid4())
    log_doc = {
        "log_id": log_id,
        "note": str(note).strip(),
        "created_at": SERVER_TIMESTAMP,
        "created_by": created_by,
    }
    ref.collection("performance_logs").document(log_id).set(log_doc)
    log.info("Performance log added | user_id=%s | log_id=%s | by=%s", user_id, log_id, created_by)
    audit_log(created_by, "ADD_PERF_LOG", f"staff/{user_id}/performance_logs/{log_id}")
    return True, "", log_doc


def list_performance_logs(user_id: str) -> list[dict]:
    """Return all performance logs for a staff member, newest first."""
    db = get_firestore()
    docs = (
        db.collection(_STAFF).document(user_id)
        .collection("performance_logs")
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )
    return [d.to_dict() for d in docs]


def delete_performance_log(user_id: str, log_id: str, deleted_by: str) -> tuple[bool, str]:
    """Delete a performance log entry."""
    db = get_firestore()
    ref = (
        db.collection(_STAFF).document(user_id)
        .collection("performance_logs").document(log_id)
    )
    if not ref.get().exists:
        return False, "Log entry not found."
    ref.delete()
    audit_log(deleted_by, "DELETE_PERF_LOG", f"staff/{user_id}/performance_logs/{log_id}")
    return True, ""
