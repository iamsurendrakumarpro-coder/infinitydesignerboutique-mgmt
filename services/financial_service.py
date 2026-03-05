"""
services/financial_service.py – Financial request business logic.

Firestore collection: financial_requests/{request_id}

Supports two request types:
  - shop_expense: Approved expenses reimbursed in settlement.
  - personal_advance: Salary advance deducted from settlement.
"""
from __future__ import annotations

import uuid
from datetime import date

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from utils.firebase_client import get_firestore
from utils.logger import get_logger, audit_log
from utils.timezone_utils import now_ist, today_ist_str, period_range

log = get_logger(__name__)

_COLLECTION = "financial_requests"
_VALID_TYPES = ("shop_expense", "personal_advance")
_VALID_STATUSES = ("pending", "approved", "rejected")


def create_request(user_id: str, data: dict) -> tuple[bool, str, dict]:
    """
    Create a financial request.

    Required keys: type, category, amount.
    Optional keys: receipt_url, notes.

    Returns (success, error_message, created_doc).
    """
    db = get_firestore()

    req_type = str(data.get("type", "")).strip()
    if req_type not in _VALID_TYPES:
        return False, f"Type must be one of: {', '.join(_VALID_TYPES)}.", {}

    category = str(data.get("category", "")).strip()
    if not category:
        return False, "Category is required.", {}

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return False, "Amount must be a valid number.", {}
    if amount <= 0:
        return False, "Amount must be greater than zero.", {}

    if req_type == "personal_advance":
        earned = get_week_to_date_earned(user_id)
        if earned is not None and amount > earned:
            return False, f"Advance amount (₹{amount:.0f}) exceeds earned salary this week (₹{earned:.0f}).", {}

    request_id = str(uuid.uuid4())
    doc = {
        "request_id": request_id,
        "user_id": user_id,
        "type": req_type,
        "category": category,
        "amount": amount,
        "receipt_url": str(data.get("receipt_url", "")).strip(),
        "notes": str(data.get("notes", "")).strip(),
        "status": "pending",
        "admin_notes": "",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    }

    db.collection(_COLLECTION).document(request_id).set(doc)
    log.info("Financial request created | request_id=%s | user_id=%s | type=%s | amount=%s",
             request_id, user_id, req_type, amount)
    audit_log(user_id, "CREATE_FINANCIAL_REQUEST", f"{_COLLECTION}/{request_id}",
              f"type={req_type}, amount={amount}")
    return True, "", doc


def get_requests(filters: dict | None = None) -> list[dict]:
    """
    List financial requests, optionally filtered.

    Supported filters: status, user_id.
    """
    db = get_firestore()
    query = db.collection(_COLLECTION)

    if filters:
        if filters.get("status") and filters["status"] in _VALID_STATUSES:
            query = query.where("status", "==", filters["status"])
        if filters.get("user_id"):
            query = query.where("user_id", "==", filters["user_id"])

    query = query.order_by("created_at", direction="DESCENDING")
    docs = query.stream()
    result = [_sanitise(d.to_dict()) for d in docs]
    log.info("get_requests | filters=%s | count=%d", filters, len(result))
    return result


def get_request(request_id: str) -> dict | None:
    """Return a single financial request or None."""
    db = get_firestore()
    doc = db.collection(_COLLECTION).document(request_id).get()
    if not doc.exists:
        return None
    return _sanitise(doc.to_dict())


def approve_request(request_id: str, admin_id: str, notes: str = "") -> tuple[bool, str]:
    """Approve a pending financial request."""
    db = get_firestore()
    ref = db.collection(_COLLECTION).document(request_id)
    doc = ref.get()
    if not doc.exists:
        return False, "Request not found."
    data = doc.to_dict()
    if data.get("status") != "pending":
        return False, f"Request is already {data.get('status')}."

    ref.update({
        "status": "approved",
        "admin_notes": str(notes).strip(),
        "reviewed_by": admin_id,
        "reviewed_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    })
    log.info("Financial request approved | request_id=%s | admin_id=%s", request_id, admin_id)
    audit_log(admin_id, "APPROVE_FINANCIAL_REQUEST", f"{_COLLECTION}/{request_id}")
    return True, ""


def reject_request(request_id: str, admin_id: str, notes: str = "") -> tuple[bool, str]:
    """Reject a pending financial request."""
    db = get_firestore()
    ref = db.collection(_COLLECTION).document(request_id)
    doc = ref.get()
    if not doc.exists:
        return False, "Request not found."
    data = doc.to_dict()
    if data.get("status") != "pending":
        return False, f"Request is already {data.get('status')}."

    ref.update({
        "status": "rejected",
        "admin_notes": str(notes).strip(),
        "reviewed_by": admin_id,
        "reviewed_at": SERVER_TIMESTAMP,
        "updated_at": SERVER_TIMESTAMP,
    })
    log.info("Financial request rejected | request_id=%s | admin_id=%s", request_id, admin_id)
    audit_log(admin_id, "REJECT_FINANCIAL_REQUEST", f"{_COLLECTION}/{request_id}")
    return True, ""


def get_week_to_date_earned(user_id: str) -> float | None:
    """
    Calculate how much salary the user has earned this week based on attendance.
    Returns None if unable to calculate (e.g. staff not found).
    """
    try:
        from services.user_service import get_staff, compute_daily_salary
        from services.attendance_service import get_attendance_history

        staff = get_staff(user_id)
        if not staff:
            return None

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
    db = get_firestore()
    from datetime import datetime
    import pytz
    IST = pytz.timezone("Asia/Kolkata")

    start_dt = datetime.combine(start, datetime.min.time())
    start_dt = IST.localize(start_dt)
    end_dt = datetime.combine(end, datetime.max.time())
    end_dt = IST.localize(end_dt)

    query = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .where("status", "==", "approved")
    )

    docs = query.stream()
    results = []
    for d in docs:
        data = d.to_dict()
        created = data.get("created_at")
        if created and hasattr(created, "date"):
            doc_date = created.date() if not hasattr(created, "astimezone") else created.astimezone(IST).date()
            if start <= doc_date <= end:
                if req_type is None or data.get("type") == req_type:
                    results.append(data)
    return results


# ── Helper ────────────────────────────────────────────────────────────────────

def _sanitise(data: dict) -> dict:
    """Convert Firestore timestamps to ISO strings."""
    from utils.timezone_utils import format_ist
    out = dict(data)
    for field in ("created_at", "updated_at", "reviewed_at"):
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
