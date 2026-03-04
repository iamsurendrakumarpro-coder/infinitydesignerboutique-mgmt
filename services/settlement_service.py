"""
services/settlement_service.py – Weekly settlement generation and retrieval.

Firestore collection: settlements/{settlement_id}

Settlement calculation:
  base_pay     = daily_salary × days_present
  overtime_pay = sum of approved overtime payouts
  expenses     = sum of approved shop_expense amounts
  advances     = sum of approved personal_advance amounts
  net_payable  = base_pay + overtime_pay + expenses - advances
"""
from __future__ import annotations

import uuid
from datetime import date

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from utils.firebase_client import get_firestore
from utils.firebase_client import get_firestore
from utils.logger import get_logger, audit_log
from utils.timezone_utils import format_ist

log = get_logger(__name__)

_COLLECTION = "settlements"


def calculate_settlement(user_id: str, week_start: date, week_end: date) -> dict:
    """
    Calculate settlement breakdown for a single staff member for a given week.

    Returns a dict with all settlement components.
    """
    from services.user_service import get_staff, compute_daily_salary
    from services.attendance_service import get_attendance_history
    from services.overtime_service import get_approved_overtime_for_period
    from services.financial_service import get_approved_requests_for_period

    staff = get_staff(user_id)
    if not staff:
        log.error("calculate_settlement: staff not found | user_id=%s", user_id)
        return {}

    weekly_salary = float(staff.get("weekly_salary", 0))
    daily_salary = compute_daily_salary(weekly_salary)

    records = get_attendance_history(user_id, week_start, week_end)
    days_present = sum(1 for r in records if r.get("punch_in"))

    base_pay = round(daily_salary * days_present, 2)

    overtime_records = get_approved_overtime_for_period(user_id, week_start, week_end)
    overtime_pay = round(sum(float(r.get("calculated_payout", 0)) for r in overtime_records), 2)

    expense_records = get_approved_requests_for_period(user_id, week_start, week_end, "shop_expense")
    expenses = round(sum(float(r.get("amount", 0)) for r in expense_records), 2)

    advance_records = get_approved_requests_for_period(user_id, week_start, week_end, "personal_advance")
    advances = round(sum(float(r.get("amount", 0)) for r in advance_records), 2)

    net_payable = round(base_pay + overtime_pay + expenses - advances, 2)

    return {
        "user_id": user_id,
        "full_name": staff.get("full_name", ""),
        "designation": staff.get("designation", ""),
        "weekly_salary": weekly_salary,
        "daily_salary": daily_salary,
        "days_present": days_present,
        "base_pay": base_pay,
        "overtime_pay": overtime_pay,
        "overtime_records_count": len(overtime_records),
        "expenses": expenses,
        "expense_records_count": len(expense_records),
        "advances": advances,
        "advance_records_count": len(advance_records),
        "net_payable": net_payable,
    }


def generate_weekly_settlement(week_start: date, week_end: date, generated_by: str) -> tuple[bool, str, list[dict]]:
    """
    Generate settlements for all active staff for the given week.

    Returns (success, error_message, list_of_settlement_dicts).
    """
    from services.user_service import list_staff

    active_staff = list_staff(status_filter="active")
    if not active_staff:
        return False, "No active staff found.", []

    db = get_firestore()
    settlements = []

    for staff in active_staff:
        user_id = staff["user_id"]
        try:
            breakdown = calculate_settlement(user_id, week_start, week_end)
            if not breakdown:
                continue

            settlement_id = str(uuid.uuid4())
            doc = {
                "settlement_id": settlement_id,
                "user_id": user_id,
                "full_name": breakdown.get("full_name", ""),
                "designation": breakdown.get("designation", ""),
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_end": week_end.strftime("%Y-%m-%d"),
                "weekly_salary": breakdown["weekly_salary"],
                "daily_salary": breakdown["daily_salary"],
                "days_present": breakdown["days_present"],
                "base_pay": breakdown["base_pay"],
                "overtime_pay": breakdown["overtime_pay"],
                "expenses": breakdown["expenses"],
                "advances": breakdown["advances"],
                "net_payable": breakdown["net_payable"],
                "generated_by": generated_by,
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
            }

            db.collection(_COLLECTION).document(settlement_id).set(doc)
            settlements.append(doc)

            log.info("Settlement generated | settlement_id=%s | user_id=%s | net=%.2f",
                     settlement_id, user_id, breakdown["net_payable"])
            audit_log(generated_by, "GENERATE_SETTLEMENT", f"{_COLLECTION}/{settlement_id}",
                      f"user={user_id}, net={breakdown['net_payable']}")

        except Exception as exc:
            log.error("Settlement generation failed | user_id=%s | error=%s", user_id, exc)

    log.info("Weekly settlement generation complete | count=%d | period=%s to %s",
             len(settlements), week_start, week_end)
    return True, "", settlements


def get_settlement(settlement_id: str) -> dict | None:
    """Return a single settlement or None."""
    db = get_firestore()
    doc = db.collection(_COLLECTION).document(settlement_id).get()
    if not doc.exists:
        return None
    return _sanitise(doc.to_dict())


def get_settlements(filters: dict | None = None) -> list[dict]:
    """
    List settlements, optionally filtered.

    Supported filters: user_id, week_start, week_end.
    """
    db = get_firestore()
    query = db.collection(_COLLECTION)

    if filters:
        if filters.get("user_id"):
            query = query.where("user_id", "==", filters["user_id"])
        if filters.get("week_start"):
            query = query.where("week_start", "==", filters["week_start"])
        if filters.get("week_end"):
            query = query.where("week_end", "==", filters["week_end"])

    query = query.order_by("created_at", direction="DESCENDING")
    docs = query.stream()
    result = [_sanitise(d.to_dict()) for d in docs]
    log.info("get_settlements | filters=%s | count=%d", filters, len(result))
    return result


def get_settlements_for_user(user_id: str) -> list[dict]:
    """Return all settlements for a specific user."""
    db = get_firestore()
    docs = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )
    return [_sanitise(d.to_dict()) for d in docs]


# ── Helper ────────────────────────────────────────────────────────────────────

def _sanitise(data: dict) -> dict:
    """Convert Firestore timestamps to IST strings."""
    out = dict(data)
    for field in ("created_at", "updated_at"):
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
