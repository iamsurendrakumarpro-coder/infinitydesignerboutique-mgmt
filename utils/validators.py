"""
utils/validators.py – Input validation helpers for the boutique app.

All public functions return (is_valid: bool, error_message: str).
On success the error_message is an empty string.
"""
from __future__ import annotations

import re
from config import get_config

_cfg = get_config()

# ── Regex patterns ─────────────────────────────────────────────────────────────
_PHONE_RE = re.compile(r"^\d{10}$")
_PIN_RE = re.compile(r"^\d{4}$")
_TIME_24_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


# ── Phone ─────────────────────────────────────────────────────────────────────

def validate_phone(phone: str | None) -> tuple[bool, str]:
    """Validate a 10-digit Indian phone number."""
    if not phone:
        return False, "Phone number is required."
    phone = str(phone).strip()
    if not _PHONE_RE.match(phone):
        return False, "Phone number must be exactly 10 digits."
    return True, ""


# ── PIN ───────────────────────────────────────────────────────────────────────

def validate_pin(pin: str | None) -> tuple[bool, str]:
    """Validate a 4-digit numeric PIN."""
    if not pin:
        return False, "PIN is required."
    pin = str(pin).strip()
    if not _PIN_RE.match(pin):
        return False, "PIN must be exactly 4 digits."
    return True, ""


# ── Name ──────────────────────────────────────────────────────────────────────

def validate_full_name(name: str | None) -> tuple[bool, str]:
    """Validate a non-empty full name (2–100 characters)."""
    if not name:
        return False, "Full name is required."
    name = str(name).strip()
    if len(name) < 2:
        return False, "Full name must be at least 2 characters."
    if len(name) > 100:
        return False, "Full name must not exceed 100 characters."
    return True, ""


# ── Designation ───────────────────────────────────────────────────────────────

def validate_designation(designation: str | None) -> tuple[bool, str]:
    """Validate staff designation against the allowed list."""
    if not designation:
        return False, "Designation is required."
    if designation not in _cfg.DESIGNATIONS:
        allowed = ", ".join(_cfg.DESIGNATIONS)
        return False, f"Designation must be one of: {allowed}."
    return True, ""


# ── Salary ────────────────────────────────────────────────────────────────────

def validate_salary(salary: str | int | float | None) -> tuple[bool, str]:
    """Validate weekly salary is a positive number."""
    if salary is None or str(salary).strip() == "":
        return False, "Weekly salary is required."
    try:
        val = float(salary)
    except (ValueError, TypeError):
        return False, "Weekly salary must be a valid number."
    if val <= 0:
        return False, "Weekly salary must be greater than zero."
    return True, ""


# ── Shift Time ────────────────────────────────────────────────────────────────

def validate_time_24h(t: str | None, field: str = "Time") -> tuple[bool, str]:
    """Validate a 24-hr time string HH:MM."""
    if not t:
        return False, f"{field} is required."
    if not _TIME_24_RE.match(str(t).strip()):
        return False, f"{field} must be in HH:MM format (24-hour, e.g. 10:00)."
    return True, ""


# ── Date ──────────────────────────────────────────────────────────────────────

def validate_date_str(d: str | None, field: str = "Date") -> tuple[bool, str]:
    """Validate a YYYY-MM-DD date string."""
    if not d:
        return False, f"{field} is required."
    try:
        from datetime import datetime
        datetime.strptime(str(d).strip(), "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, f"{field} must be in YYYY-MM-DD format."


# ── Status ────────────────────────────────────────────────────────────────────

def validate_status(status: str | None) -> tuple[bool, str]:
    """Validate staff status value."""
    allowed = _cfg.STAFF_STATUSES
    if not status or status not in allowed:
        return False, f"Status must be one of: {', '.join(allowed)}."
    return True, ""


# ── Composite helpers ─────────────────────────────────────────────────────────

def validate_admin_create(data: dict) -> dict[str, str]:
    """
    Validate data dict for admin creation.
    Returns a dict of {field: error_message}.  Empty dict = all valid.
    """
    errors: dict[str, str] = {}
    ok, msg = validate_full_name(data.get("full_name"))
    if not ok:
        errors["full_name"] = msg
    ok, msg = validate_phone(data.get("phone_number"))
    if not ok:
        errors["phone_number"] = msg
    return errors


def validate_staff_create(data: dict) -> dict[str, str]:
    """Validate data dict for staff creation."""
    errors: dict[str, str] = {}

    ok, msg = validate_full_name(data.get("full_name"))
    if not ok:
        errors["full_name"] = msg

    ok, msg = validate_phone(data.get("phone_number"))
    if not ok:
        errors["phone_number"] = msg

    ok, msg = validate_designation(data.get("designation"))
    if not ok:
        errors["designation"] = msg

    ok, msg = validate_date_str(data.get("joining_date"), "Joining date")
    if not ok:
        errors["joining_date"] = msg

    ok, msg = validate_time_24h(data.get("standard_login_time"), "Login time")
    if not ok:
        errors["standard_login_time"] = msg

    ok, msg = validate_time_24h(data.get("standard_logout_time"), "Logout time")
    if not ok:
        errors["standard_logout_time"] = msg

    if data.get("emergency_contact"):
        ok, msg = validate_phone(data.get("emergency_contact"))
        if not ok:
            errors["emergency_contact"] = "Emergency contact: " + msg

    ok, msg = validate_salary(data.get("weekly_salary"))
    if not ok:
        errors["weekly_salary"] = msg

    ok, msg = validate_pin(data.get("temp_pin"))
    if not ok:
        errors["temp_pin"] = msg

    return errors


def validate_staff_update(data: dict) -> dict[str, str]:
    """Validate data dict for staff update (phone is immutable – not checked)."""
    errors: dict[str, str] = {}

    if "full_name" in data:
        ok, msg = validate_full_name(data.get("full_name"))
        if not ok:
            errors["full_name"] = msg

    if "designation" in data:
        ok, msg = validate_designation(data.get("designation"))
        if not ok:
            errors["designation"] = msg

    if "joining_date" in data:
        ok, msg = validate_date_str(data.get("joining_date"), "Joining date")
        if not ok:
            errors["joining_date"] = msg

    if "standard_login_time" in data:
        ok, msg = validate_time_24h(data.get("standard_login_time"), "Login time")
        if not ok:
            errors["standard_login_time"] = msg

    if "standard_logout_time" in data:
        ok, msg = validate_time_24h(data.get("standard_logout_time"), "Logout time")
        if not ok:
            errors["standard_logout_time"] = msg

    if "emergency_contact" in data and data["emergency_contact"]:
        ok, msg = validate_phone(data.get("emergency_contact"))
        if not ok:
            errors["emergency_contact"] = "Emergency contact: " + msg

    if "weekly_salary" in data:
        ok, msg = validate_salary(data.get("weekly_salary"))
        if not ok:
            errors["weekly_salary"] = msg

    return errors
