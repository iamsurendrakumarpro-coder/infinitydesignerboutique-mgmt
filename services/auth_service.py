"""
services/auth_service.py - Authentication business logic.

Responsibilities
----------------
* Verify phone + PIN for both admins and staff
* Hash / verify PINs with bcrypt
* Manage first-login flag
* Build session payload
"""
from __future__ import annotations

import bcrypt

from services.repositories.auth_repository import get_auth_repository
from utils.logger import get_logger, audit_log
from utils.timezone_utils import now_utc

log = get_logger(__name__)


def _repo():
    return get_auth_repository()


def _db_timestamp():
    return now_utc()


# -- PIN helpers ---------------------------------------------------------------

def hash_pin(plain_pin: str) -> str:
    """Return bcrypt hash of a plain-text 4-digit PIN."""
    hashed = bcrypt.hashpw(plain_pin.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Return True if plain_pin matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_pin.encode("utf-8"), hashed_pin.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.error("PIN verification error: %s", exc)
        return False


# -- Login ---------------------------------------------------------------------

def authenticate_user(phone_number: str, plain_pin: str) -> dict | None:
    """
    Attempt login for a given phone + PIN.

    Search order: admins -> staff.
    Returns a session-ready dict on success; None on failure.

    Session dict shape::

        {
            "user_id":       str,
            "role":          "admin" | "staff",
            "full_name":     str,
            "phone_number":  str,
            "is_first_login": bool,
            "status":        str,          # staff only
            "is_root":       bool,         # admin only
        }
    """
    repo = _repo()
    phone_number = str(phone_number).strip()

    log.info("Login attempt | phone=%s", phone_number)

    # -- 1. Check admins collection --------------------------------------------
    data = repo.get_admin_by_phone(phone_number)
    if data:
        stored_hash = data.get("pin_hash", "")
        if not stored_hash:
            log.warning("Admin has no PIN hash stored | user_id=%s", data["user_id"])
            return None

        if not verify_pin(plain_pin, stored_hash):
            log.warning("Invalid PIN for admin | user_id=%s", data["user_id"])
            audit_log(data["user_id"], "LOGIN_FAILED", f"admins/{data['user_id']}", "Wrong PIN")
            return None

        log.info("Admin login success | user_id=%s | name=%s", data["user_id"], data.get("full_name"))
        audit_log(data["user_id"], "LOGIN_SUCCESS", f"admins/{data['user_id']}")
        return {
            "user_id": data["user_id"],
            "role": "admin",
            "full_name": data.get("full_name", ""),
            "phone_number": data.get("phone_number", ""),
            "is_first_login": data.get("is_first_login", False),
            "is_root": data.get("is_root", False),
        }

    # -- 2. Check staff collection ---------------------------------------------
    data = repo.get_staff_by_phone(phone_number)
    if data:
        status = data.get("status", "active")

        if status == "deactivated":
            log.warning("Login attempt by deactivated staff | user_id=%s", data["user_id"])
            audit_log(data["user_id"], "LOGIN_BLOCKED", f"staff/{data['user_id']}", "Account deactivated")
            return {"blocked": True, "reason": "Your account has been deactivated. Please contact the admin."}

        if status == "inactive":
            log.warning("Login attempt by inactive staff | user_id=%s", data["user_id"])
            audit_log(data["user_id"], "LOGIN_BLOCKED", f"staff/{data['user_id']}", "Account inactive")
            return {"blocked": True, "reason": "Your account is currently inactive. Please contact the admin."}

        stored_hash = data.get("pin_hash", "")
        if not stored_hash:
            log.warning("Staff has no PIN hash stored | user_id=%s", data["user_id"])
            return None

        if not verify_pin(plain_pin, stored_hash):
            log.warning("Invalid PIN for staff | user_id=%s", data["user_id"])
            audit_log(data["user_id"], "LOGIN_FAILED", f"staff/{data['user_id']}", "Wrong PIN")
            return None

        log.info("Staff login success | user_id=%s | name=%s", data["user_id"], data.get("full_name"))
        audit_log(data["user_id"], "LOGIN_SUCCESS", f"staff/{data['user_id']}")
        return {
            "user_id": data["user_id"],
            "role": "staff",
            "full_name": data.get("full_name", ""),
            "phone_number": data.get("phone_number", ""),
            "is_first_login": data.get("is_first_login", False),
            "status": status,
            "designation": data.get("designation", ""),
        }

    log.warning("No user found for phone | phone=%s", phone_number)
    return None


# -- PIN change ----------------------------------------------------------------

def change_pin(user_id: str, role: str, old_pin: str | None, new_pin: str, is_first_login: bool = False) -> tuple[bool, str]:
    """
    Change a user's PIN.

    Parameters
    ----------
    user_id       : Firestore document ID.
    role          : 'admin' | 'staff'.
    old_pin       : Current PIN (required unless is_first_login).
    new_pin       : New 4-digit PIN.
    is_first_login: Skip old_pin verification on first-time login.

    Returns (success, error_message).
    """
    repo = _repo()
    collection = "admins" if role == "admin" else "staff"
    data = repo.get_user_with_hash(role, user_id)

    if data is None:
        log.error("change_pin: user not found | user_id=%s | role=%s", user_id, role)
        return False, "User not found."

    if not is_first_login:
        if not old_pin:
            return False, "Current PIN is required."
        stored_hash = data.get("pin_hash", "")
        if not verify_pin(old_pin, stored_hash):
            log.warning("change_pin: wrong current PIN | user_id=%s", user_id)
            return False, "Current PIN is incorrect."

    new_hash = hash_pin(new_pin)
    repo.update_pin(role, user_id, new_hash, False, _db_timestamp())

    log.info("PIN changed successfully | user_id=%s | role=%s", user_id, role)
    audit_log(user_id, "PIN_CHANGED", f"{collection}/{user_id}")
    return True, ""


# -- Admin PIN reset for staff -------------------------------------------------

def admin_reset_staff_pin(admin_id: str, staff_id: str, temp_pin: str) -> tuple[bool, str]:
    """
    Admin sets a temporary PIN for a staff member.
    The staff member will be forced to change it on next login.

    Returns (success, error_message).
    """
    repo = _repo()
    data = repo.get_user_with_hash("staff", staff_id)

    if data is None:
        log.error("admin_reset_staff_pin: staff not found | staff_id=%s", staff_id)
        return False, "Staff member not found."

    new_hash = hash_pin(temp_pin)
    repo.update_pin("staff", staff_id, new_hash, True, _db_timestamp())

    log.info("Admin reset staff PIN | admin_id=%s | staff_id=%s", admin_id, staff_id)
    audit_log(admin_id, "ADMIN_RESET_PIN", f"staff/{staff_id}")
    return True, ""
