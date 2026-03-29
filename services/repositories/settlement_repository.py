"""Settlement persistence adapters for Firebase and PostgreSQL."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from utils.db.postgres_client import get_postgres_connection
from utils.firebase_client import get_firestore
from utils.logger import get_logger

log = get_logger(__name__)
_COLLECTION = "settlements"


@dataclass
class SettlementRepository:
    """Persistence contract for settlement storage backends."""

    def get_latest_prior_with_carry(self, user_id: str, period_end: str) -> dict | None:
        raise NotImplementedError

    def find_by_user_and_period(self, user_id: str, week_start: str, week_end: str) -> dict | None:
        raise NotImplementedError

    def save(self, settlement: dict) -> None:
        raise NotImplementedError

    def get_by_id(self, settlement_id: str) -> dict | None:
        raise NotImplementedError

    def list_settlements(self, filters: dict | None = None) -> list[dict]:
        raise NotImplementedError

    def list_for_user(self, user_id: str) -> list[dict]:
        raise NotImplementedError


class FirestoreSettlementRepository(SettlementRepository):
    def get_latest_prior_with_carry(self, user_id: str, period_end: str) -> dict | None:
        db = get_firestore()
        docs = (
            db.collection(_COLLECTION)
            .where("user_id", "==", user_id)
            .where("week_end", "<", period_end)
            .order_by("week_end", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
        return None

    def find_by_user_and_period(self, user_id: str, week_start: str, week_end: str) -> dict | None:
        db = get_firestore()
        docs = list(
            db.collection(_COLLECTION)
            .where("user_id", "==", user_id)
            .where("week_start", "==", week_start)
            .where("week_end", "==", week_end)
            .limit(1)
            .stream()
        )
        if not docs:
            return None
        return docs[0].to_dict()

    def save(self, settlement: dict) -> None:
        db = get_firestore()
        settlement_id = settlement["settlement_id"]
        db.collection(_COLLECTION).document(settlement_id).set(settlement)

    def get_by_id(self, settlement_id: str) -> dict | None:
        db = get_firestore()
        doc = db.collection(_COLLECTION).document(settlement_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    def list_settlements(self, filters: dict | None = None) -> list[dict]:
        db = get_firestore()
        query = db.collection(_COLLECTION)

        if filters:
            if filters.get("user_id"):
                query = query.where("user_id", "==", filters["user_id"])
            if filters.get("week_start") and filters.get("week_end"):
                query = query.where("week_end", ">=", filters["week_start"]).where("week_end", "<=", filters["week_end"])
            elif filters.get("week_start"):
                query = query.where("week_end", ">=", filters["week_start"])
            elif filters.get("week_end"):
                query = query.where("week_end", "<=", filters["week_end"])

        docs = query.order_by("created_at", direction="DESCENDING").stream()
        return [d.to_dict() for d in docs]

    def list_for_user(self, user_id: str) -> list[dict]:
        db = get_firestore()
        docs = (
            db.collection(_COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]


class PostgresSettlementRepository(SettlementRepository):
    _UPSERT_SQL = """
        INSERT INTO settlements (
            settlement_id, user_id, full_name, designation, salary_type, settlement_cycle,
            week_start, week_end, weekly_salary, monthly_salary, daily_salary, days_present,
            base_pay, overtime_pay, expenses, advances, net_payable,
            hours_worked, ot_hours, carry_forward_in, amount_settled, carry_forward,
            settlement_status, generated_by, settled_by, created_at, updated_at
        ) VALUES (
            %(settlement_id)s, %(user_id)s, %(full_name)s, %(designation)s, %(salary_type)s, %(settlement_cycle)s,
            %(week_start)s, %(week_end)s, %(weekly_salary)s, %(monthly_salary)s, %(daily_salary)s, %(days_present)s,
            %(base_pay)s, %(overtime_pay)s, %(expenses)s, %(advances)s, %(net_payable)s,
            %(hours_worked)s, %(ot_hours)s, %(carry_forward_in)s, %(amount_settled)s, %(carry_forward)s,
            %(settlement_status)s, %(generated_by)s, %(settled_by)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (settlement_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            full_name = EXCLUDED.full_name,
            designation = EXCLUDED.designation,
            salary_type = EXCLUDED.salary_type,
            settlement_cycle = EXCLUDED.settlement_cycle,
            week_start = EXCLUDED.week_start,
            week_end = EXCLUDED.week_end,
            weekly_salary = EXCLUDED.weekly_salary,
            monthly_salary = EXCLUDED.monthly_salary,
            daily_salary = EXCLUDED.daily_salary,
            days_present = EXCLUDED.days_present,
            base_pay = EXCLUDED.base_pay,
            overtime_pay = EXCLUDED.overtime_pay,
            expenses = EXCLUDED.expenses,
            advances = EXCLUDED.advances,
            net_payable = EXCLUDED.net_payable,
            hours_worked = EXCLUDED.hours_worked,
            ot_hours = EXCLUDED.ot_hours,
            carry_forward_in = EXCLUDED.carry_forward_in,
            amount_settled = EXCLUDED.amount_settled,
            carry_forward = EXCLUDED.carry_forward,
            settlement_status = EXCLUDED.settlement_status,
            generated_by = EXCLUDED.generated_by,
            settled_by = EXCLUDED.settled_by,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at
    """

    @staticmethod
    def _fetchone_dict(cur) -> dict[str, Any] | None:
        row = cur.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))

    @staticmethod
    def _fetchall_dicts(cur) -> list[dict[str, Any]]:
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]

    def _norm_row(self, row: dict[str, Any] | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)

        for key in ("week_start", "week_end"):
            value = out.get(key)
            if isinstance(value, date):
                out[key] = value.isoformat()

        for key in (
            "weekly_salary",
            "monthly_salary",
            "daily_salary",
            "base_pay",
            "overtime_pay",
            "expenses",
            "advances",
            "net_payable",
            "hours_worked",
            "ot_hours",
            "carry_forward_in",
            "amount_settled",
            "carry_forward",
        ):
            value = out.get(key)
            if isinstance(value, Decimal):
                out[key] = float(value)

        return out

    def _query_one(self, sql: str, params: tuple[Any, ...]) -> dict | None:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = self._fetchone_dict(cur)
                return self._norm_row(row)

    def _query_many(self, sql: str, params: tuple[Any, ...]) -> list[dict]:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = self._fetchall_dicts(cur)
                return [self._norm_row(r) for r in rows]

    def get_latest_prior_with_carry(self, user_id: str, period_end: str) -> dict | None:
        return self._query_one(
            """
            SELECT *
            FROM settlements
            WHERE user_id = %s AND week_end < %s
            ORDER BY week_end DESC
            LIMIT 1
            """,
            (user_id, period_end),
        )

    def find_by_user_and_period(self, user_id: str, week_start: str, week_end: str) -> dict | None:
        return self._query_one(
            """
            SELECT *
            FROM settlements
            WHERE user_id = %s
              AND week_start = %s
              AND week_end = %s
            LIMIT 1
            """,
            (user_id, week_start, week_end),
        )

    def save(self, settlement: dict) -> None:
        payload = {
            "settlement_id": settlement.get("settlement_id"),
            "user_id": settlement.get("user_id"),
            "full_name": settlement.get("full_name"),
            "designation": settlement.get("designation"),
            "salary_type": settlement.get("salary_type") or "weekly",
            "settlement_cycle": settlement.get("settlement_cycle") or settlement.get("salary_type") or "weekly",
            "week_start": settlement.get("week_start"),
            "week_end": settlement.get("week_end"),
            "weekly_salary": settlement.get("weekly_salary"),
            "monthly_salary": settlement.get("monthly_salary"),
            "daily_salary": settlement.get("daily_salary"),
            "days_present": settlement.get("days_present"),
            "base_pay": settlement.get("base_pay", 0),
            "overtime_pay": settlement.get("overtime_pay", 0),
            "expenses": settlement.get("expenses", 0),
            "advances": settlement.get("advances", 0),
            "net_payable": settlement.get("net_payable", 0),
            "hours_worked": settlement.get("hours_worked", 0),
            "ot_hours": settlement.get("ot_hours", 0),
            "carry_forward_in": settlement.get("carry_forward_in", 0),
            "amount_settled": settlement.get("amount_settled", 0),
            "carry_forward": settlement.get("carry_forward", 0),
            "settlement_status": settlement.get("settlement_status") or "pending",
            "generated_by": settlement.get("generated_by"),
            "settled_by": settlement.get("settled_by"),
            "created_at": settlement.get("created_at"),
            "updated_at": settlement.get("updated_at"),
        }
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self._UPSERT_SQL, payload)
            conn.commit()

    def get_by_id(self, settlement_id: str) -> dict | None:
        return self._query_one("SELECT * FROM settlements WHERE settlement_id = %s LIMIT 1", (settlement_id,))

    def list_settlements(self, filters: dict | None = None) -> list[dict]:
        where: list[str] = []
        params: list[Any] = []

        if filters:
            if filters.get("user_id"):
                where.append("user_id = %s")
                params.append(filters["user_id"])
            if filters.get("week_start") and filters.get("week_end"):
                where.append("week_end >= %s AND week_end <= %s")
                params.extend([filters["week_start"], filters["week_end"]])
            elif filters.get("week_start"):
                where.append("week_end >= %s")
                params.append(filters["week_start"])
            elif filters.get("week_end"):
                where.append("week_end <= %s")
                params.append(filters["week_end"])

        sql = "SELECT * FROM settlements"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC NULLS LAST, week_end DESC"

        return self._query_many(sql, tuple(params))

    def list_for_user(self, user_id: str) -> list[dict]:
        return self._query_many(
            """
            SELECT *
            FROM settlements
            WHERE user_id = %s
            ORDER BY created_at DESC NULLS LAST, week_end DESC
            """,
            (user_id,),
        )


def get_settlement_repository() -> SettlementRepository:
    provider = os.getenv("APP_DB_PROVIDER", "firebase").strip().lower()
    if provider == "postgres":
        return PostgresSettlementRepository()
    return FirestoreSettlementRepository()
