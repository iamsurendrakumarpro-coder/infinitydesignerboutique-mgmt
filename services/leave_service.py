"""
services/leave_service.py - Leave management business logic.

Persistence model
-----------------
leave_requests table

Document schema::

    {
        "request_id":       str (UUID),
        "user_id":          str,
        "leave_type":       "half_day" | "full_day" | "multiple_days",
        "start_date":       "YYYY-MM-DD",
        "end_date":         "YYYY-MM-DD",
        "half_day_period":  "morning" | "afternoon" | None,
        "reason":           str,
        "status":           "pending" | "approved" | "rejected" | "cancelled",
        "admin_notes":      str,
        "reviewed_by":      str | None,
        "reviewed_at":      Timestamp | None,
        "total_days":       float (0.5 for half, 1.0 for full, N for multiple),
        "created_at":       Timestamp,
        "updated_at":       Timestamp,
    }

Rules
-----
* Staff can only apply for future or today's leave.
* Staff can cancel their own pending leave.
* Admins can approve or reject any pending leave.
* Cannot have overlapping approved leave for the same staff.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from services.repositories.leave_repository import get_leave_repository
from services.requester_context import build_requester_context_map
from utils.logger import get_logger, audit_log
from utils.timezone_utils import today_ist, now_utc

log = get_logger(__name__)

_VALID_TYPES = ("half_day", "full_day", "multiple_days")
_VALID_STATUSES = ("pending", "approved", "rejected", "cancelled")
_VALID_PERIODS = ("morning", "afternoon")


def _repo():
    return get_leave_repository()


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

    # Backward-compatible aliases used by templates.
    out["staff_name"] = requester_name
    out["full_name"] = requester_name

    return out


def create_leave_request(user_id: str, data: dict) -> tuple[bool, str, dict]:
    """
    Create a new leave request for a staff member.

    Returns (success, error_message, request_dict).
    """
    leave_type = data.get("leave_type", "").strip()
    if leave_type not in _VALID_TYPES:
        return False, f"Invalid leave type. Must be one of: {', '.join(_VALID_TYPES)}", {}

    start_date_str = data.get("start_date", "").strip()
    if not start_date_str:
        return False, "Start date is required.", {}

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "Invalid start date format. Use YYYY-MM-DD.", {}

    today = today_ist()
    if start_date < today:
        return False, "Cannot apply leave for past dates.", {}

    # End date
    if leave_type == "multiple_days":
        end_date_str = data.get("end_date", "").strip()
        if not end_date_str:
            return False, "End date is required for multiple days leave.", {}
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return False, "Invalid end date format. Use YYYY-MM-DD.", {}
        if end_date < start_date:
            return False, "End date cannot be before start date.", {}
        if end_date == start_date:
            return False, "For single day leave, use 'full_day' type.", {}
        total_days = float((end_date - start_date).days + 1)
    elif leave_type == "half_day":
        end_date = start_date
        total_days = 0.5
    else:  # full_day
        end_date = start_date
        total_days = 1.0

    # Half day period validation
    half_day_period = None
    if leave_type == "half_day":
        half_day_period = data.get("half_day_period", "").strip()
        if half_day_period not in _VALID_PERIODS:
            return False, f"Half day period must be 'morning' or 'afternoon'.", {}

    reason = (data.get("reason", "") or "").strip()
    if len(reason) > 500:
        return False, "Reason must be 500 characters or less.", {}

    # Check for overlapping approved / pending leave
    conflict = _repo().find_overlapping(user_id, start_date, end_date)
    if conflict:
        return False, f"You already have a {conflict['status']} leave from {conflict['start_date']} to {conflict['end_date']}.", {}

    request_id = str(uuid.uuid4())
    ts = _db_timestamp()
    doc_data = {
        "request_id": request_id,
        "user_id": user_id,
        "leave_type": leave_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "half_day_period": half_day_period,
        "reason": reason,
        "status": "pending",
        "admin_notes": "",
        "reviewed_by": None,
        "reviewed_at": None,
        "total_days": total_days,
        "created_at": ts,
        "updated_at": ts,
    }

    _repo().save(request_id, doc_data)
    log.info("Leave request created | user_id=%s | type=%s | %s to %s | days=%.1f",
             user_id, leave_type, start_date, end_date, total_days)
    audit_log(user_id, "LEAVE_REQUEST_CREATED", f"leave_requests/{request_id}")

    return True, "", doc_data


def get_leave_requests(filters: dict | None = None) -> list[dict]:
    """
    Get leave requests with optional filters.

    Supported filters: user_id, status.
    """
    rows = _repo().list_requests(filters)
    context_map = build_requester_context_map(d.get("user_id") for d in rows)
    results = []
    for data in rows:
        results.append(_enrich_leave(data, context_map))
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    log.debug("get_leave_requests | filters=%s | count=%d", filters, len(results))
    return results


def get_leave_request(request_id: str) -> dict | None:
    """Get a single leave request by ID."""
    data = _repo().get_by_id(request_id)
    if data is None:
        return None
    context_map = build_requester_context_map([data.get("user_id")])
    return _enrich_leave(data, context_map)


def review_leave(request_id: str, action: str, admin_id: str, admin_notes: str = "") -> tuple[bool, str, dict]:
    """
    Approve or reject a leave request.

    Returns (success, error_message, updated_dict).
    """
    if action not in ("approve", "reject"):
        return False, "Action must be 'approve' or 'reject'.", {}

    data = _repo().get_by_id(request_id)
    if data is None:
        return False, "Leave request not found.", {}

    if data.get("status") != "pending":
        return False, f"Cannot {action} a leave that is already {data.get('status')}.", {}

    new_status = "approved" if action == "approve" else "rejected"
    ts = _db_timestamp()
    _repo().update_review(request_id, new_status, admin_id, admin_notes, ts, ts)

    data["status"] = new_status
    data["admin_notes"] = admin_notes
    data["reviewed_by"] = admin_id

    log.info("Leave %sd | request_id=%s | admin_id=%s", action, request_id, admin_id)
    audit_log(admin_id, f"LEAVE_{action.upper()}D", f"leave_requests/{request_id}")

    return True, "", data


def cancel_leave(request_id: str, user_id: str) -> tuple[bool, str]:
    """
    Cancel a pending leave request (staff can only cancel their own).

    Returns (success, error_message).
    """
    data = _repo().get_by_id(request_id)
    if data is None:
        return False, "Leave request not found."

    if data.get("user_id") != user_id:
        return False, "You can only cancel your own leave requests."
    if data.get("status") != "pending":
        return False, f"Cannot cancel a leave that is already {data.get('status')}."

    _repo().cancel(request_id, _db_timestamp())

    log.info("Leave cancelled | request_id=%s | user_id=%s", request_id, user_id)
    audit_log(user_id, "LEAVE_CANCELLED", f"leave_requests/{request_id}")

    return True, ""


def get_leaves_for_date(target_date: date | None = None) -> list[dict]:
    """
    Get all approved leaves that cover a specific date.
    Used for dashboard to show who is on leave today.
    """
    if target_date is None:
        target_date = today_ist()
    rows = _repo().get_approved_for_date(target_date)
    context_map = build_requester_context_map(d.get("user_id") for d in rows)
    results = []
    for data in rows:
        results.append(_enrich_leave(data, context_map))
    log.debug("get_leaves_for_date | date=%s | count=%d", target_date, len(results))
    return results


def get_pending_leave_count() -> int:
    """Get count of pending leave requests (for badge)."""
    return _repo().count_pending()


def _enrich_leave(data: dict, context_map: dict[str, dict] | None = None) -> dict:
    """Add requester identity details for leave approval context."""
    data = _attach_requester_context(data, context_map)
    if not data.get("designation"):
        data["designation"] = data.get("requester_designation", "")

    # Serialise timestamps
    for key in ("created_at", "updated_at", "reviewed_at"):
        val = data.get(key)
        if val and hasattr(val, "isoformat"):
            data[key] = val.isoformat()

    return data
