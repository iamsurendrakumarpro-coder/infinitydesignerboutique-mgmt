"""
services/settlement_service.py - Settlement generation and retrieval.

Firestore collection: settlements/{settlement_id}

Settlement calculation:
  base_pay     = daily_salary * days_present
  overtime_pay = sum of approved overtime payouts
  expenses     = sum of approved shop_expense amounts
  advances     = sum of approved personal_advance amounts
  net_payable  = base_pay + overtime_pay + expenses - advances

Partial settlement:
  amount_settled     = how much was actually paid
  settlement_status  = pending | partial | settled
  carry_forward      = net_payable - amount_settled (carried to next period)
"""
from __future__ import annotations

import calendar
import os
import uuid
from datetime import date, timedelta

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from services.repositories.settlement_repository import get_settlement_repository
from utils.logger import get_logger, audit_log
from utils.timezone_utils import format_ist, now_utc
from services.settings_service import get_working_config

log = get_logger(__name__)

_COLLECTION = "settlements"


def _repo():
    return get_settlement_repository()


def _db_timestamp():
    provider = os.getenv("APP_DB_PROVIDER", "firebase").strip().lower()
    if provider == "postgres":
        return now_utc()
    return SERVER_TIMESTAMP


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


def _get_carry_forward(user_id: str, period_end: str) -> float:
    """Return the carry-forward amount from the most recent prior settlement for a user."""
    settlement = _repo().get_latest_prior_with_carry(user_id, period_end)
    if settlement:
        cf = float(settlement.get("carry_forward", 0))
        if cf > 0:
            return cf
    return 0.0


def _build_settlement_doc(breakdown: dict, week_start: date, week_end: date,
                          generated_by: str, settlement_id: str | None = None,
                          cycle: str = "weekly",
                          carry_forward_in: float = 0.0) -> dict:
    """Build a Firestore settlement document from a calculated breakdown."""
    net = breakdown["net_payable"] + carry_forward_in
    sid = settlement_id or str(uuid.uuid4())
    ts = _db_timestamp()
    return {
        "settlement_id": sid,
        "user_id": breakdown["user_id"],
        "full_name": breakdown.get("full_name", ""),
        "designation": breakdown.get("designation", ""),
        "salary_type": breakdown.get("salary_type", cycle),
        "settlement_cycle": cycle,
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
        "net_payable": round(net, 2),
        "hours_worked": breakdown["hours_worked"],
        "ot_hours": breakdown["ot_hours"],
        "carry_forward_in": round(carry_forward_in, 2),
        "amount_settled": 0,
        "carry_forward": round(net, 2),
        "settlement_status": "pending",
        "generated_by": generated_by,
        "created_at": ts,
        "updated_at": ts,
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

    repo = _repo()
    settlements = []

    for staff in weekly_staff:
        user_id = staff["user_id"]
        try:
            breakdown = calculate_settlement(user_id, week_start, week_end)
            if not breakdown:
                continue

            carry_in = _get_carry_forward(user_id, week_start.strftime("%Y-%m-%d"))

            existing_data = repo.find_by_user_and_period(
                user_id,
                week_start.strftime("%Y-%m-%d"),
                week_end.strftime("%Y-%m-%d"),
            )
            if existing_data:
                # Update existing settlement
                settlement_id = existing_data.get("settlement_id")
                net = breakdown["net_payable"] + carry_in
                existing_data.update({
                    "full_name": breakdown.get("full_name", ""),
                    "designation": breakdown.get("designation", ""),
                    "salary_type": breakdown.get("salary_type", "weekly"),
                    "settlement_cycle": "weekly",
                    "weekly_salary": breakdown.get("weekly_salary"),
                    "monthly_salary": breakdown.get("monthly_salary"),
                    "daily_salary": breakdown["daily_salary"],
                    "days_present": breakdown["days_present"],
                    "base_pay": breakdown["base_pay"],
                    "overtime_pay": breakdown["overtime_pay"],
                    "expenses": breakdown["expenses"],
                    "advances": breakdown["advances"],
                    "net_payable": round(net, 2),
                    "hours_worked": breakdown["hours_worked"],
                    "ot_hours": breakdown["ot_hours"],
                    "carry_forward_in": round(carry_in, 2),
                    "generated_by": generated_by,
                    "updated_at": _db_timestamp(),
                })
                # Recalculate carry_forward if already partially settled
                amt_settled = float(existing_data.get("amount_settled", 0))
                existing_data["carry_forward"] = round(net - amt_settled, 2)
                if amt_settled >= net:
                    existing_data["settlement_status"] = "settled"
                elif amt_settled > 0:
                    existing_data["settlement_status"] = "partial"
                else:
                    existing_data["settlement_status"] = "pending"

                repo.save(existing_data)
                settlements.append(existing_data)
                log.info("Settlement updated | settlement_id=%s | user_id=%s | net=%.2f",
                         settlement_id, user_id, net)
                audit_log(generated_by, "UPDATE_SETTLEMENT", f"{_COLLECTION}/{settlement_id}",
                          f"user={user_id}, net={net}")
            else:
                # Create new settlement
                doc = _build_settlement_doc(breakdown, week_start, week_end,
                                            generated_by, cycle="weekly",
                                            carry_forward_in=carry_in)
                repo.save(doc)
                settlements.append(doc)
                log.info("Settlement generated | settlement_id=%s | user_id=%s | net=%.2f",
                         doc["settlement_id"], user_id, doc["net_payable"])
                audit_log(generated_by, "GENERATE_SETTLEMENT", f"{_COLLECTION}/{doc['settlement_id']}",
                          f"user={user_id}, net={doc['net_payable']}")
        except Exception as exc:
            log.error("Settlement generation failed | user_id=%s | error=%s", user_id, exc)

    log.info("Weekly settlement generation complete | count=%d | period=%s to %s",
             len(settlements), week_start, week_end)
    settlements = [_sanitise_settlement(s) for s in settlements]
    return True, "", settlements


def generate_monthly_settlement(month_start: date, month_end: date, generated_by: str) -> tuple[bool, str, list[dict]]:
    """
    Generate settlements for all active staff with monthly settlement_cycle.

    Returns (success, error_message, list_of_settlement_dicts).
    """
    from services.user_service import list_staff

    active_staff = list_staff(status_filter="active")
    if not active_staff:
        return False, "No active staff found.", []

    monthly_staff = [s for s in active_staff if s.get("settlement_cycle") == "monthly"]
    if not monthly_staff:
        return False, "No active staff with monthly settlement cycle found.", []

    repo = _repo()
    settlements = []

    for staff in monthly_staff:
        user_id = staff["user_id"]
        try:
            breakdown = calculate_settlement(user_id, month_start, month_end)
            if not breakdown:
                continue

            carry_in = _get_carry_forward(user_id, month_start.strftime("%Y-%m-%d"))

            existing_data = repo.find_by_user_and_period(
                user_id,
                month_start.strftime("%Y-%m-%d"),
                month_end.strftime("%Y-%m-%d"),
            )
            if existing_data:
                settlement_id = existing_data.get("settlement_id")
                net = breakdown["net_payable"] + carry_in
                existing_data.update({
                    "full_name": breakdown.get("full_name", ""),
                    "designation": breakdown.get("designation", ""),
                    "salary_type": breakdown.get("salary_type", "monthly"),
                    "settlement_cycle": "monthly",
                    "weekly_salary": breakdown.get("weekly_salary"),
                    "monthly_salary": breakdown.get("monthly_salary"),
                    "daily_salary": breakdown["daily_salary"],
                    "days_present": breakdown["days_present"],
                    "base_pay": breakdown["base_pay"],
                    "overtime_pay": breakdown["overtime_pay"],
                    "expenses": breakdown["expenses"],
                    "advances": breakdown["advances"],
                    "net_payable": round(net, 2),
                    "hours_worked": breakdown["hours_worked"],
                    "ot_hours": breakdown["ot_hours"],
                    "carry_forward_in": round(carry_in, 2),
                    "generated_by": generated_by,
                    "updated_at": _db_timestamp(),
                })
                amt_settled = float(existing_data.get("amount_settled", 0))
                existing_data["carry_forward"] = round(net - amt_settled, 2)
                if amt_settled >= net:
                    existing_data["settlement_status"] = "settled"
                elif amt_settled > 0:
                    existing_data["settlement_status"] = "partial"
                else:
                    existing_data["settlement_status"] = "pending"

                repo.save(existing_data)
                settlements.append(existing_data)
                log.info("Monthly settlement updated | id=%s | user=%s | net=%.2f",
                         settlement_id, user_id, net)
            else:
                doc = _build_settlement_doc(breakdown, month_start, month_end,
                                            generated_by, cycle="monthly",
                                            carry_forward_in=carry_in)
                repo.save(doc)
                settlements.append(doc)
                log.info("Monthly settlement generated | id=%s | user=%s | net=%.2f",
                         doc["settlement_id"], user_id, doc["net_payable"])
        except Exception as exc:
            log.error("Monthly settlement generation failed | user=%s | error=%s", user_id, exc)

    log.info("Monthly settlement generation complete | count=%d | period=%s to %s",
             len(settlements), month_start, month_end)
    settlements = [_sanitise_settlement(s) for s in settlements]
    return True, "", settlements


def mark_settlement(settlement_id: str, amount_settled: float, settled_by: str) -> dict | None:
    """
    Mark a settlement as settled (full or partial).

    If amount_settled < net_payable, status = 'partial' and carry_forward = remainder.
    If amount_settled >= net_payable, status = 'settled' and carry_forward = 0.
    """
    repo = _repo()
    data = repo.get_by_id(settlement_id)
    if not data:
        return None

    net = float(data.get("net_payable", 0))
    amount_settled = round(max(0, amount_settled), 2)
    carry = round(max(0, net - amount_settled), 2)

    if amount_settled >= net:
        status = "settled"
        carry = 0
    elif amount_settled > 0:
        status = "partial"
    else:
        status = "pending"

    data.update({
        "amount_settled": amount_settled,
        "settlement_status": status,
        "carry_forward": carry,
        "settled_by": settled_by,
        "updated_at": _db_timestamp(),
    })
    repo.save(data)

    log.info("mark_settlement | id=%s | amount=%.2f | status=%s | carry=%.2f",
             settlement_id, amount_settled, status, carry)
    audit_log(settled_by, "MARK_SETTLEMENT", f"{_COLLECTION}/{settlement_id}",
              f"amount={amount_settled}, status={status}, carry={carry}")
    return _sanitise(data)


def get_settlement(settlement_id: str) -> dict | None:
    """Return a single settlement or None."""
    data = _repo().get_by_id(settlement_id)
    if not data:
        log.debug("get_settlement | settlement_id=%s | found=false", settlement_id)
        return None
    log.debug("get_settlement | settlement_id=%s | found=true", settlement_id)
    return _sanitise(data)


def get_settlements(filters: dict | None = None) -> list[dict]:
    """
    List settlements, optionally filtered.

    Supported filters: user_id, week_start, week_end.
    """
    settlements = [_sanitise(s) for s in _repo().list_settlements(filters)]
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
    results = [_sanitise(s) for s in _repo().list_for_user(user_id)]
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
    # Preserve numeric values
    for num_field in ("hours_worked", "ot_hours", "amount_settled", "carry_forward", "carry_forward_in"):
        if num_field in out and isinstance(out[num_field], (int, float)):
            out[num_field] = float(out[num_field])
    # Default settlement tracking fields
    out.setdefault("settlement_status", "pending")
    out.setdefault("amount_settled", 0)
    out.setdefault("carry_forward", float(out.get("net_payable", 0)))
    out.setdefault("carry_forward_in", 0)
    out.setdefault("settlement_cycle", out.get("salary_type", "weekly"))
    return out
