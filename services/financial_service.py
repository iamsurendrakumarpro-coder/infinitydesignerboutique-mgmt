"""
services/financial_service.py - Financial request business logic.

PostgreSQL table: financial_requests

Supports two request types:
    - shop_expense: Approved shop expenses that are reimbursed as a separate stream.
    - personal_advance: Salary advance deducted from payroll settlement.

All monetary amounts are stored in INR (Indian Rupees).
All timestamps are serialised to IST strings before being returned to the API layer
via _sanitise().
"""
from __future__ import annotations

import uuid
from datetime import date

from services.repositories.financial_repository import get_financial_repository
from services.requester_context import build_requester_context_map
from utils.storage_provider import generate_download_url
from utils.logger import get_logger, audit_log
from utils.timezone_utils import period_range, now_utc

log = get_logger(__name__)

_VALID_TYPES = ("shop_expense", "personal_advance")
_VALID_STATUSES = ("pending", "approved", "rejected")
_VALID_REIMBURSEMENT_STATUSES = ("pending", "paid", "not_applicable")


def _repo():
    return get_financial_repository()


def _db_timestamp():
    return now_utc()


def _attach_requester_context(data: dict, context_map: dict[str, dict] | None = None) -> dict:
    """Attach requester profile fields used by admin approval cards."""
    out = dict(data)
    uid = out.get("user_id")

    requester_name = "Unknown Staff"
    requester_phone = ""
    requester_role = "staff"
    requester_designation = ""

    if uid and context_map:
        ctx = context_map.get(str(uid))
        if ctx:
            requester_name = ctx.get("requester_name") or requester_name
            requester_phone = ctx.get("requester_phone") or ""
            requester_role = ctx.get("requester_role") or "staff"
            requester_designation = ctx.get("requester_designation") or ""

    out["requester_user_id"] = uid
    out["requester_name"] = requester_name
    out["requester_phone"] = requester_phone
    out["requester_role"] = requester_role
    out["requester_designation"] = requester_designation

    # Backward-compatible aliases used across templates.
    out["employee_name"] = requester_name
    out["staff_name"] = requester_name
    out["full_name"] = requester_name

    return out


def create_request(user_id: str, data: dict) -> tuple[bool, str, dict]:
    """
    Create a financial request.

    Required keys: type, category, amount.
    Optional keys: receipt_url, notes.

    Returns (success, error_message, created_doc).
    """
    req_type = str(data.get("type", "")).strip()
    if req_type not in _VALID_TYPES:
        return False, f"Type must be one of: {', '.join(_VALID_TYPES)}.", {}

    category = str(data.get("category", "")).strip()
    if req_type == "shop_expense" and not category:
        return False, "Category is required for shop expenses.", {}

    gcs_path = str(data.get("gcs_path", "")).strip()
    # Bill image is required for shop expenses except the 'food' category (Food / Tea)
    if req_type == "shop_expense" and category != 'food' and not gcs_path:
        return False, "Bill image is required for shop expenses.", {}
    # For personal_advance, category is optional

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return False, "Amount must be a valid number.", {}
    if amount <= 0:
        return False, "Amount must be greater than zero.", {}

    if req_type == "personal_advance":
        from services.user_service import get_staff
        staff = get_staff(user_id)
        weekly_salary = float(staff.get("weekly_salary", 0)) if staff else 0
        if weekly_salary > 0 and amount > weekly_salary:
            return False, f"Advance amount (INR {amount:.0f}) exceeds weekly salary (INR {weekly_salary:.0f}).", {}

    request_id = str(uuid.uuid4())
    notes_val = str(data.get("notes", "")).strip()
    log.info("create_request | notes=%s | data=%s", notes_val, data)
    ts = _db_timestamp()
    doc = {
        "request_id": request_id,
        "user_id": user_id,
        "type": req_type,
        "category": category,
        "amount": amount,
        # Store only the GCS path, not a signed URL
        "receipt_gcs_path": gcs_path,
        "notes": notes_val,
        "status": "pending",
        "admin_notes": "",
        "reviewed_by": None,
        "reviewed_at": None,
        "reimbursement_status": "pending" if req_type == "shop_expense" else "not_applicable",
        "reimbursed_by": None,
        "reimbursed_at": None,
        "reimbursement_notes": "",
        "created_at": ts,
        "updated_at": ts,
    }

    _repo().save(request_id, doc)
    log.info("Financial request created | request_id=%s | user_id=%s | type=%s | amount=%s",
             request_id, user_id, req_type, amount)
    audit_log(user_id, "CREATE_FINANCIAL_REQUEST", f"financial_requests/{request_id}",
              f"type={req_type}, amount={amount}")
    # Omit timestamps before returning
    doc.pop("created_at", None)
    doc.pop("updated_at", None)
    return True, "", doc


def get_requests(filters: dict | None = None) -> list[dict]:
    """
    List financial requests, optionally filtered.

    Supported filters: status, user_id.
    """
    safe_filters: dict = {}
    if filters:
        if filters.get("status") and filters["status"] in _VALID_STATUSES:
            safe_filters["status"] = filters["status"]
        if filters.get("user_id"):
            safe_filters["user_id"] = filters["user_id"]
        if filters.get("category"):
            safe_filters["category"] = filters["category"]
        if filters.get("type") and filters["type"] in _VALID_TYPES:
            safe_filters["type"] = filters["type"]
        if filters.get("reimbursement_status") and filters["reimbursement_status"] in _VALID_REIMBURSEMENT_STATUSES:
            safe_filters["reimbursement_status"] = filters["reimbursement_status"]
        if filters.get("start_date"):
            safe_filters["start_date"] = filters["start_date"]
        if filters.get("end_date"):
            safe_filters["end_date"] = filters["end_date"]

    docs = _repo().list_requests(safe_filters or None)
    context_map = build_requester_context_map(d.get("user_id") for d in docs)
    result = []
    for data in docs:
        data = _attach_requester_context(data, context_map)
        gcs_path = data.get("receipt_gcs_path")
        if gcs_path:
            try:
                data["receipt_url"] = generate_download_url(gcs_path, expiration_minutes=60)
            except Exception as e:
                log.error("Failed to generate signed URL for %s: %s", gcs_path, e)
                data["receipt_url"] = None
        else:
            data["receipt_url"] = None
        result.append(_sanitise(data))
    log.info("get_requests | filters=%s | count=%d", filters, len(result))
    return result


def get_request(request_id: str) -> dict | None:
    """Return a single financial request or None."""
    data = _repo().get_by_id(request_id)
    if data is None:
        log.debug("get_request | request_id=%s | found=false", request_id)
        return None
    log.debug("get_request | request_id=%s | found=true", request_id)
    context_map = build_requester_context_map([data.get("user_id")])
    data = _attach_requester_context(data, context_map)
    gcs_path = data.get("receipt_gcs_path")
    if gcs_path:
        try:
            data["receipt_url"] = generate_download_url(gcs_path, expiration_minutes=60)
        except Exception as e:
            log.error("Failed to generate signed URL for %s: %s", gcs_path, e)
            data["receipt_url"] = None
    else:
        data["receipt_url"] = None
    return _sanitise(data)


def approve_request(request_id: str, admin_id: str, notes: str = "") -> tuple[bool, str]:
    """Approve a pending financial request."""
    data = _repo().request_exists(request_id)
    if data is None:
        return False, "Request not found."
    if data.get("status") != "pending":
        return False, f"Request is already {data.get('status')}."

    ts = _db_timestamp()
    _repo().update_review(request_id, "approved", admin_id, str(notes).strip(), ts, ts)
    log.info("Financial request approved | request_id=%s | admin_id=%s", request_id, admin_id)
    audit_log(admin_id, "APPROVE_FINANCIAL_REQUEST", f"financial_requests/{request_id}")
    return True, ""


def reject_request(request_id: str, admin_id: str, notes: str = "") -> tuple[bool, str]:
    """Reject a pending financial request."""
    data = _repo().request_exists(request_id)
    if data is None:
        return False, "Request not found."
    if data.get("status") != "pending":
        return False, f"Request is already {data.get('status')}."

    ts = _db_timestamp()
    _repo().update_review(request_id, "rejected", admin_id, str(notes).strip(), ts, ts)
    log.info("Financial request rejected | request_id=%s | admin_id=%s", request_id, admin_id)
    audit_log(admin_id, "REJECT_FINANCIAL_REQUEST", f"financial_requests/{request_id}")
    return True, ""


def mark_reimbursed(request_id: str, admin_id: str, notes: str = "") -> tuple[bool, str]:
    """Mark an approved shop expense as reimbursed (paid)."""
    data = _repo().request_exists(request_id)
    if data is None:
        return False, "Request not found."
    if data.get("type") != "shop_expense":
        return False, "Only shop expense requests can be reimbursed."
    if data.get("status") != "approved":
        return False, "Only approved shop expenses can be reimbursed."
    if data.get("reimbursement_status") == "paid":
        return False, "Request is already marked as reimbursed."

    ts = _db_timestamp()
    _repo().update_reimbursement(
        request_id,
        reimbursement_status="paid",
        reimbursed_by=admin_id,
        reimbursement_notes=str(notes).strip(),
        reimbursed_at=ts,
        updated_at=ts,
    )
    log.info("Financial reimbursement marked paid | request_id=%s | admin_id=%s", request_id, admin_id)
    audit_log(admin_id, "MARK_REIMBURSED_FINANCIAL_REQUEST", f"financial_requests/{request_id}")
    return True, ""


def get_week_to_date_earned(user_id: str) -> float | None:
    """
    Calculate how much salary the user has earned this week based on attendance.
    Returns None if unable to calculate (e.g. staff not found).

    For monthly staff, uses monthly_salary / MONTHLY_WORKING_DAYS for daily rate.
    For weekly staff, uses weekly_salary / WORKING_DAYS_PER_WEEK for daily rate.
    """
    try:
        from services.user_service import get_staff, compute_daily_salary
        from services.attendance_service import get_attendance_history

        staff = get_staff(user_id)
        if not staff:
            return None

        salary_type = staff.get("salary_type", "weekly")
        weekly_salary = float(staff.get("weekly_salary", 0))
        if weekly_salary <= 0:
            return 0.0
        daily_salary = compute_daily_salary(weekly_salary)

        start, end = period_range("weekly")
        records = get_attendance_history(user_id, start, end)
        days_present = sum(1 for r in records if r.get("punch_in"))

        return daily_salary * days_present
    except Exception as exc:
        log.error("get_week_to_date_earned failed | user_id=%s | error=%s", user_id, exc)
        return None


def get_approved_requests_for_period(user_id: str, start: date, end: date, req_type: str | None = None) -> list[dict]:
    """Return approved financial requests for a user in a date range."""
    results = _repo().get_approved_for_period(user_id, start, end, req_type)
    log.debug("get_approved_requests_for_period | user_id=%s | start=%s | end=%s | type=%s | count=%d",
              user_id, start, end, req_type, len(results))
    return results


# -- Helper --------------------------------------------------------------------

def _sanitise(data: dict) -> dict:
    """Convert timestamp fields to IST strings."""
    from utils.timezone_utils import format_ist
    out = dict(data)
    for field in ("created_at", "updated_at", "reviewed_at", "reimbursed_at"):
        val = out.get(field)
        if val is None:
            out[field] = None
        elif hasattr(val, "isoformat"):
            out[field] = format_ist(val)
        else:
            try:
                out[field] = format_ist(val)
            except Exception:
                out[field] = str(val)
    return out
