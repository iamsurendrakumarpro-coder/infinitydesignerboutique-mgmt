"""
services/settlement_service.py - Weekly settlement generation and retrieval.

Firestore collection: settlements/{settlement_id}

Settlement calculation:
  base_pay     = daily_salary * days_present
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
from utils.logger import get_logger, audit_log
from utils.timezone_utils import format_ist
from services.settings_service import get_working_config

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

    # Determine salary type and calculate daily salary accordingly
    salary_type = staff.get("salary_type", "weekly")
    if salary_type == "monthly":
        monthly_salary = float(staff.get("monthly_salary", 0))
        weekly_salary = None
        daily_salary = compute_daily_salary(monthly_salary, "monthly")
    else:
        weekly_salary = float(staff.get("weekly_salary", 0))
        monthly_salary = None
        daily_salary = compute_daily_salary(weekly_salary, "weekly")

    records = get_attendance_history(user_id, week_start, week_end)
    working_config = get_working_config()
    standard_hours = working_config["standard_hours_per_day"]
    base_pay = 0.0
    days_present = 0
    total_hours_worked = 0.0
    total_ot_hours = 0.0
    for r in records:
        mins = r.get("duration_minutes", 0)
        if mins > 0:
            days_present += 1
            hours_worked = mins / 60.0
            if hours_worked < 1:
                hours_worked = round(mins) / 60.0
            base_pay += daily_salary * (hours_worked / standard_hours)
            total_hours_worked += hours_worked
            if hours_worked > standard_hours:
                total_ot_hours += hours_worked - standard_hours
    base_pay = round(base_pay, 2)
    # Always recalculate and include hours_worked and ot_hours from attendance
    if not records:
        total_hours_worked = 0.0
        total_ot_hours = 0.0
    else:
        total_hours_worked = round(total_hours_worked, 2)
        total_ot_hours = round(total_ot_hours, 2)

    overtime_records = get_approved_overtime_for_period(user_id, week_start, week_end)
    overtime_pay = round(sum(float(r.get("calculated_payout", 0)) for r in overtime_records), 2)

    expense_records = get_approved_requests_for_period(user_id, week_start, week_end, "shop_expense")
    expenses = round(sum(float(r.get("amount", 0)) for r in expense_records), 2)

    advance_records = get_approved_requests_for_period(user_id, week_start, week_end, "personal_advance")
    advances = round(sum(float(r.get("amount", 0)) for r in advance_records), 2)

    net_payable = round(base_pay + overtime_pay + expenses - advances, 2)

    log.info("calculate_settlement | user_id=%s | salary_type=%s | days=%d | base=%.2f | overtime=%.2f | expenses=%.2f | advances=%.2f | net=%.2f",
             user_id, salary_type, days_present, base_pay, overtime_pay, expenses, advances, net_payable)
    return {
        "user_id": user_id,
        "full_name": staff.get("full_name", ""),
        "designation": staff.get("designation", ""),
        "salary_type": salary_type,
        "weekly_salary": weekly_salary,
        "monthly_salary": monthly_salary,
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
        "hours_worked": round(total_hours_worked, 2),
        "ot_hours": round(total_ot_hours, 2),
    }


def generate_weekly_settlement(week_start: date, week_end: date, generated_by: str) -> tuple[bool, str, list[dict]]:
    """
    Generate settlements for all active staff with weekly settlement_cycle for the given week.

    Staff with settlement_cycle="monthly" are skipped in weekly batch.

    Returns (success, error_message, list_of_settlement_dicts).
    """
    from services.user_service import list_staff

    active_staff = list_staff(status_filter="active")
    if not active_staff:
        return False, "No active staff found.", []

    # Filter to only weekly settlement cycle staff
    weekly_staff = [s for s in active_staff if s.get("settlement_cycle", "weekly") == "weekly"]
    if not weekly_staff:
        return False, "No active staff with weekly settlement cycle found.", []

    db = get_firestore()
    settlements = []

    for staff in weekly_staff:
        user_id = staff["user_id"]
        try:
            breakdown = calculate_settlement(user_id, week_start, week_end)
            if not breakdown:
                continue

            # Check for existing settlement for this user and week
            existing_query = (
                db.collection(_COLLECTION)
                .where("user_id", "==", user_id)
                .where("week_start", "==", week_start.strftime("%Y-%m-%d"))
                .where("week_end", "==", week_end.strftime("%Y-%m-%d"))
                .limit(1)
            )
            existing_docs = list(existing_query.stream())
            if existing_docs:
                # Update existing settlement
                settlement_id = existing_docs[0].id
                doc = existing_docs[0].to_dict()
                doc.update({
                    "full_name": breakdown.get("full_name", ""),
                    "designation": breakdown.get("designation", ""),
                    "salary_type": breakdown.get("salary_type", "weekly"),
                    "weekly_salary": breakdown.get("weekly_salary"),
                    "monthly_salary": breakdown.get("monthly_salary"),
                    "daily_salary": breakdown["daily_salary"],
                    "days_present": breakdown["days_present"],
                    "base_pay": breakdown["base_pay"],
                    "overtime_pay": breakdown["overtime_pay"],
                    "expenses": breakdown["expenses"],
                    "advances": breakdown["advances"],
                    "net_payable": breakdown["net_payable"],
                    "hours_worked": breakdown["hours_worked"],
                    "ot_hours": breakdown["ot_hours"],
                    "generated_by": generated_by,
                    "updated_at": SERVER_TIMESTAMP,
                })
                db.collection(_COLLECTION).document(settlement_id).set(doc)
                settlements.append(doc)
                log.info("Settlement updated | settlement_id=%s | user_id=%s | net=%.2f",
                         settlement_id, user_id, breakdown["net_payable"])
                audit_log(generated_by, "UPDATE_SETTLEMENT", f"{_COLLECTION}/{settlement_id}",
                          f"user={user_id}, net={breakdown['net_payable']}")
            else:
                # Create new settlement
                settlement_id = str(uuid.uuid4())
                doc = {
                    "settlement_id": settlement_id,
                    "user_id": user_id,
                    "full_name": breakdown.get("full_name", ""),
                    "designation": breakdown.get("designation", ""),
                    "salary_type": breakdown.get("salary_type", "weekly"),
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "week_end": week_end.strftime("%Y-%m-%d"),
                    "weekly_salary": breakdown.get("weekly_salary"),
                    "monthly_salary": breakdown.get("monthly_salary"),
                    "daily_salary": breakdown["daily_salary"],
                    "days_present": breakdown["days_present"],
                    "base_pay": breakdown["base_pay"],
                    "overtime_pay": breakdown["overtime_pay"],
                    "expenses": breakdown["expenses"],
                    "advances": breakdown["advances"],
                    "net_payable": breakdown["net_payable"],
                    "hours_worked": breakdown["hours_worked"],
                    "ot_hours": breakdown["ot_hours"],
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
    # Sanitize settlements for JSON serialization
    settlements = [_sanitise_settlement(s) for s in settlements]
    return True, "", settlements


def get_settlement(settlement_id: str) -> dict | None:
    """Return a single settlement or None."""
    db = get_firestore()
    doc = db.collection(_COLLECTION).document(settlement_id).get()
    if not doc.exists:
        log.debug("get_settlement | settlement_id=%s | found=false", settlement_id)
        return None
    log.debug("get_settlement | settlement_id=%s | found=true", settlement_id)
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
        # Support week range: settlements where week_end is between week_start and week_end
        if filters.get("week_start") and filters.get("week_end"):
            query = query.where("week_end", ">=", filters["week_start"]).where("week_end", "<=", filters["week_end"])
        elif filters.get("week_start"):
            query = query.where("week_end", ">=", filters["week_start"])
        elif filters.get("week_end"):
            query = query.where("week_end", "<=", filters["week_end"])

    query = query.order_by("created_at", direction="DESCENDING")
    docs = query.stream()
    settlements = [_sanitise(d.to_dict()) for d in docs]
    # Deduplicate: keep only the latest settlement per user per week
    deduped = {}
    for s in settlements:
        key = (s.get("user_id"), s.get("week_start"), s.get("week_end"))
        if key not in deduped or s.get("created_at","") > deduped[key].get("created_at",""):
            deduped[key] = s
    result = list(deduped.values())
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
    results = [_sanitise(d.to_dict()) for d in docs]
    log.debug("get_settlements_for_user | user_id=%s | count=%d", user_id, len(results))
    return results


# -- Helper --------------------------------------------------------------------

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

def _sanitise_settlement(data: dict) -> dict:
    """Convert Firestore timestamps and Sentinel values to ISO strings or None, preserve numeric fields."""
    out = dict(data)
    for ts_field in ("created_at", "updated_at"):
        val = out.get(ts_field)
        if val is None:
            out[ts_field] = None
        elif hasattr(val, "isoformat"):
            out[ts_field] = format_ist(val)
        elif hasattr(val, "to_datetime"):
            out[ts_field] = format_ist(val.to_datetime())
        elif str(val).startswith("<google.cloud.firestore_v1._helpers.Sentinel"):
            out[ts_field] = None
        else:
            try:
                out[ts_field] = str(val)
            except Exception:
                out[ts_field] = None
    # Preserve numeric values for hours_worked and ot_hours
    for num_field in ("hours_worked", "ot_hours"):
        if num_field in out and isinstance(out[num_field], (int, float)):
            out[num_field] = float(out[num_field])
    return out
