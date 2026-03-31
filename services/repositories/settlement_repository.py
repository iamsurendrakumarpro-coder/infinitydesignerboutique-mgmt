"""Settlement persistence adapter for PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from utils.db.postgres_client import get_postgres_connection
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

    def list_settlements(
        self,
        filters: dict | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        raise NotImplementedError

    def count_settlements(self, filters: dict | None = None) -> int:
        raise NotImplementedError

    def list_for_user(self, user_id: str) -> list[dict]:
        raise NotImplementedError


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

    @staticmethod
    def _build_filters(filters: dict | None = None) -> tuple[list[str], list[Any]]:
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

        return where, params

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

    def list_settlements(
        self,
        filters: dict | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        where, params = self._build_filters(filters)

        inner_sql = """
            SELECT DISTINCT ON (user_id, week_start, week_end) *
            FROM settlements
        """
        if where:
            inner_sql += " WHERE " + " AND ".join(where)
        inner_sql += " ORDER BY user_id, week_start, week_end, created_at DESC NULLS LAST, settlement_id DESC"

        sql = f"""
            SELECT *
            FROM ({inner_sql}) dedup
            ORDER BY created_at DESC NULLS LAST, week_end DESC
        """

        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), max(int(offset), 0)])

        return self._query_many(sql, tuple(params))

    def count_settlements(self, filters: dict | None = None) -> int:
        where, params = self._build_filters(filters)

        inner_sql = """
            SELECT DISTINCT ON (user_id, week_start, week_end) settlement_id
            FROM settlements
        """
        if where:
            inner_sql += " WHERE " + " AND ".join(where)
        inner_sql += " ORDER BY user_id, week_start, week_end, created_at DESC NULLS LAST, settlement_id DESC"

        sql = f"SELECT COUNT(*) AS total_count FROM ({inner_sql}) dedup"

        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                row = self._fetchone_dict(cur)
                return int(row.get("total_count", 0) if row else 0)

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
    return PostgresSettlementRepository()
