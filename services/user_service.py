"""
services/user_service.py - User management business logic.

Handles creation, retrieval, updates, status changes, gallery management,
and performance-log management for both admins and staff.

Firestore structure
-------------------
admins/{user_id}                              - Admin profile documents
staff/{user_id}                               - Staff profile documents
staff/{user_id}/work_gallery/{image_id}       - Gallery images (metadata + Storage path)
staff/{user_id}/performance_logs/{log_id}     - Performance notes added by admins

Phone uniqueness is enforced by querying both admins and staff
collections directly (no separate index collection required).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from services.auth_service import hash_pin
from utils.firebase_client import get_firestore
from utils.storage_provider import upload_bytes, delete_object, generate_download_url
from utils.logger import get_logger, audit_log
from utils.timezone_utils import now_utc, today_ist_str
from services.settings_service import (
    get_app_config,
    get_working_config,
    get_salary_types,
    get_settlement_cycles,
    get_staff_statuses,
)

log = get_logger(__name__)

# -- Collection constants ------------------------------------------------------
_ADMINS = "admins"
_STAFF  = "staff"


def compute_daily_salary(
    salary: float,
    salary_type: str = "weekly",
) -> float:
    """
    Compute daily salary based on salary type.

    For weekly staff: weekly_salary / working_days_per_week (default 6)
    For monthly staff: monthly_salary / monthly_working_days (default 26)
    """
    working_config = get_working_config()
    if salary_type == "monthly":
        return round(salary / working_config["monthly_working_days"], 2)
    return round(salary / working_config["working_days_per_week"], 2)


# -- Phone uniqueness ----------------------------------------------------------

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


# -- Admin CRUD ----------------------------------------------------------------

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


# -- Staff CRUD ----------------------------------------------------------------

def create_staff(data: dict, created_by: str) -> tuple[bool, str, dict]:
    """
    Create a new staff member.

    Required keys in data::

        full_name, phone_number, designation, joining_date,
        standard_login_time, standard_logout_time,
        emergency_contact (optional), temp_pin

    Salary fields (one required based on salary_type)::

        salary_type: "weekly" | "monthly" (default "weekly")
        weekly_salary: required if salary_type == "weekly"
        monthly_salary: required if salary_type == "monthly"
        settlement_cycle: "weekly" | "monthly" (admin-configurable)

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

    # Get dynamic settings
    salary_types = get_salary_types()
    settlement_cycles = get_settlement_cycles()
    app_config = get_app_config()

    # Salary type and settlement cycle
    salary_type = str(data.get("salary_type", "weekly")).strip()
    if salary_type not in salary_types:
        salary_type = "weekly"

    settlement_cycle = str(data.get("settlement_cycle", salary_type)).strip()
    if settlement_cycle not in settlement_cycles:
        settlement_cycle = salary_type

    # Compute salary fields based on salary_type
    if salary_type == "monthly":
        monthly_salary = float(data.get("monthly_salary", 0))
        weekly_salary = None
        daily_salary = compute_daily_salary(monthly_salary, "monthly")
    else:
        weekly_salary = float(data.get("weekly_salary", 0))
        monthly_salary = None
        daily_salary = compute_daily_salary(weekly_salary, "weekly")

    doc = {
        "user_id": user_id,
        "full_name": str(data["full_name"]).strip(),
        "phone_number": phone,
        "designation": str(data["designation"]).strip(),
        "joining_date": joining_date,
        "standard_login_time": str(data.get("standard_login_time", app_config.get("default_login_time", "10:00"))).strip(),
        "standard_logout_time": str(data.get("standard_logout_time", app_config.get("default_logout_time", "19:00"))).strip(),
        "emergency_contact": str(data.get("emergency_contact", "")).strip(),
        "salary_type": salary_type,
        "settlement_cycle": settlement_cycle,
        "weekly_salary": weekly_salary,
        "monthly_salary": monthly_salary,
        "daily_salary": daily_salary,
        "skills": data.get("skills", []) if isinstance(data.get("skills"), list) else [],
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
        "Staff created | user_id=%s | phone=%s | designation=%s | salary_type=%s | by=%s",
        user_id, phone, doc["designation"], salary_type, created_by,
    )
    audit_log(created_by, "CREATE_STAFF", f"staff/{user_id}", f"phone={phone}")
    doc.pop("pin_hash", None)
    # Remove Firestore SERVER_TIMESTAMP fields before returning
    doc.pop("created_at", None)
    doc.pop("updated_at", None)
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

    # Get dynamic settings
    salary_types = get_salary_types()
    settlement_cycles = get_settlement_cycles()

    # Guarantee salary_type and settlement_cycle defaults
    if "salary_type" not in data or data["salary_type"] not in salary_types:
        data["salary_type"] = "weekly"
    if "settlement_cycle" not in data or data["settlement_cycle"] not in settlement_cycles:
        data["settlement_cycle"] = data["salary_type"]

    # Guarantee all required fields for frontend
    if "joining_date" not in data or not data["joining_date"]:
        data["joining_date"] = "-"
    if "weekly_salary" not in data:
        data["weekly_salary"] = None
    if "monthly_salary" not in data:
        data["monthly_salary"] = None
    if "daily_salary" not in data or not data["daily_salary"]:
        # Compute from appropriate salary field
        salary_type = data.get("salary_type", "weekly")
        if salary_type == "monthly" and data.get("monthly_salary"):
            try:
                data["daily_salary"] = compute_daily_salary(float(data["monthly_salary"]), "monthly")
            except Exception:
                data["daily_salary"] = None
        elif data.get("weekly_salary"):
            try:
                data["daily_salary"] = compute_daily_salary(float(data["weekly_salary"]), "weekly")
            except Exception:
                data["daily_salary"] = None
        else:
            data["daily_salary"] = None
    if "skills" not in data or not isinstance(data["skills"], list):
        data["skills"] = []
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

    current_data = doc.to_dict()

    # Prevent phone number change
    data.pop("phone_number", None)
    data.pop("pin_hash", None)
    data.pop("user_id", None)
    data.pop("role", None)
    data.pop("created_at", None)
    data.pop("is_root", None)

    # Handle skills - ensure list
    if "skills" in data and isinstance(data["skills"], str):
        data["skills"] = [s.strip() for s in data["skills"].split(",") if s.strip()]

    # Get dynamic settings
    salary_types = get_salary_types()
    settlement_cycles = get_settlement_cycles()

    # Handle salary_type change
    salary_type = data.get("salary_type", current_data.get("salary_type", "weekly"))
    if salary_type not in salary_types:
        salary_type = "weekly"
    data["salary_type"] = salary_type

    # Handle settlement_cycle
    if "settlement_cycle" in data:
        if data["settlement_cycle"] not in settlement_cycles:
            data["settlement_cycle"] = salary_type

    # Numeric coercion for salary fields and daily_salary recomputation
    if salary_type == "monthly":
        if "monthly_salary" in data:
            data["monthly_salary"] = float(data["monthly_salary"])
            data["daily_salary"] = compute_daily_salary(data["monthly_salary"], "monthly")
        elif "weekly_salary" in data:
            # If switching to monthly but only weekly provided, ignore weekly
            data.pop("weekly_salary", None)
    else:
        if "weekly_salary" in data:
            data["weekly_salary"] = float(data["weekly_salary"])
            data["daily_salary"] = compute_daily_salary(data["weekly_salary"], "weekly")
        elif "monthly_salary" in data:
            # If switching to weekly but only monthly provided, ignore monthly
            data.pop("monthly_salary", None)

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
    allowed = get_staff_statuses()
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


# -- Skills --------------------------------------------------------------------

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


def upload_staff_govt_proof(
    user_id: str,
    file_bytes: bytes,
    filename: str,
    uploaded_by: str,
    content_type: str | None = None,
) -> tuple[bool, str, dict]:
    """
    Upload a staff government-proof attachment and store metadata in profile.

    Returns (success, error_message, proof_metadata).
    """
    db = get_firestore()
    ref = db.collection(_STAFF).document(user_id)
    if not ref.get().exists:
        return False, "Staff member not found.", {}

    proof_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    storage_path = f"govt_proofs/{user_id}/{proof_id}.{ext}"

    resolved_content_type = (content_type or "").strip() or "application/octet-stream"
    up_ok, up_err, _up_meta = upload_bytes(
        storage_path=storage_path,
        file_bytes=file_bytes,
        content_type=resolved_content_type,
        make_public=False,
    )
    if not up_ok:
        log.error("Govt proof upload failed | user_id=%s | error=%s", user_id, up_err)
        return False, f"Proof upload failed: {up_err}", {}

    log.info("Govt proof uploaded | user_id=%s | proof_id=%s | path=%s", user_id, proof_id, storage_path)

    proof_doc = {
        "proof_id": proof_id,
        "filename": str(filename or "document").strip(),
        "storage_path": storage_path,
        "content_type": resolved_content_type,
        "size_bytes": len(file_bytes),
        "uploaded_by": uploaded_by,
        "uploaded_at": SERVER_TIMESTAMP,
    }
    ref.update({"govt_proof": proof_doc, "updated_at": SERVER_TIMESTAMP})
    audit_log(uploaded_by, "UPLOAD_GOVT_PROOF", f"staff/{user_id}", detail=f"proof_id={proof_id}")

    # Return JSON-safe metadata.
    proof_meta = dict(proof_doc)
    proof_meta.pop("uploaded_at", None)
    return True, "", proof_meta


# -- Work Gallery --------------------------------------------------------------

def upload_gallery_image(user_id: str, file_bytes: bytes, filename: str, caption: str, uploaded_by: str) -> tuple[bool, str, dict]:
    """
    Upload an image to configured storage and record metadata in Firestore.

    Returns (success, error_message, gallery_item_dict).
    """
    db = get_firestore()
    image_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    storage_path = f"gallery/{user_id}/{image_id}.{ext}"

    content_type = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp") else "application/octet-stream"
    if ext == "jpg":
        content_type = "image/jpeg"

    up_ok, up_err, up_meta = upload_bytes(
        storage_path=storage_path,
        file_bytes=file_bytes,
        content_type=content_type,
        make_public=False,
    )
    if not up_ok:
        log.error("Gallery upload failed | user_id=%s | error=%s", user_id, up_err)
        return False, f"Image upload failed: {up_err}", {}

    image_url = up_meta.get("public_url") or ""
    log.info("Gallery image uploaded | user_id=%s | image_id=%s | path=%s", user_id, image_id, storage_path)

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
    result: list[dict] = []
    for d in docs:
        item = d.to_dict()
        path = item.get("storage_path")
        if path:
            try:
                item["image_url"] = generate_download_url(path, expiration_minutes=60)
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not generate gallery signed URL | path=%s | error=%s", path, exc)
                item["image_url"] = item.get("image_url") or ""
        result.append(item)
    return result


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

    # Delete from configured storage provider.
    if storage_path:
        deleted, err = delete_object(storage_path)
        if deleted:
            log.info("Gallery image deleted from storage | path=%s", storage_path)
        else:
            log.warning("Could not delete storage blob | path=%s | error=%s", storage_path, err)

    ref.delete()
    audit_log(deleted_by, "GALLERY_DELETE", f"staff/{user_id}/work_gallery/{image_id}")
    return True, ""


# -- Performance Logs ----------------------------------------------------------

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
