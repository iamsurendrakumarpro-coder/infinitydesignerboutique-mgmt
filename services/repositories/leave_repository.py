"""
services/repositories/leave_repository.py

Leave request persistence adapter for PostgreSQL.

Table: leave_requests
"""

from __future__ import annotations

import abc
from datetime import date, datetime
from decimal import Decimal

from utils.db.postgres_client import get_postgres_connection
from utils.timezone_utils import now_utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_row(row: dict) -> dict:
    """Normalise types: Decimal → float, date → ISO string.
    Datetimes are left as Python objects so _enrich_leave() can isoformat() them.
    """
    result: dict = {}
    for k, v in row.items():
        if isinstance(v, date) and not isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    return result


_COLUMNS = [
    "request_id", "user_id", "leave_type", "start_date", "end_date",
    "half_day_period", "reason", "status", "admin_notes", "reviewed_by",
    "reviewed_at", "total_days", "created_at", "updated_at",
]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class LeaveRepository(abc.ABC):

    @abc.abstractmethod
    def save(self, request_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def get_by_id(self, request_id: str) -> dict | None: ...

    @abc.abstractmethod
    def list_requests(self, filters: dict | None = None) -> list[dict]: ...

    @abc.abstractmethod
    def find_overlapping(
        self, user_id: str, start_date: date, end_date: date
    ) -> dict | None:
        """Return first overlapping pending/approved leave dict, or None."""
        ...

    @abc.abstractmethod
    def update_review(
        self,
        request_id: str,
        status: str,
        admin_id: str,
        notes: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None: ...

    @abc.abstractmethod
    def cancel(self, request_id: str, updated_at: datetime) -> None: ...

    @abc.abstractmethod
    def get_approved_for_date(self, target_date: date) -> list[dict]: ...

    @abc.abstractmethod
    def count_pending(self) -> int: ...


# ---------------------------------------------------------------------------
# Postgres implementation
# ---------------------------------------------------------------------------

class PostgresLeaveRepository(LeaveRepository):

    def save(self, request_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO leave_requests
                        (request_id, user_id, leave_type, start_date, end_date,
                         half_day_period, reason, status, admin_notes, reviewed_by,
                         reviewed_at, total_days, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s::date, %s::date,
                         %s, %s, %s, %s, %s,
                         %s, %s, %s, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        status          = EXCLUDED.status,
                        admin_notes     = EXCLUDED.admin_notes,
                        reviewed_by     = EXCLUDED.reviewed_by,
                        reviewed_at     = EXCLUDED.reviewed_at,
                        updated_at      = EXCLUDED.updated_at
                    """,
                    (
                        request_id,
                        doc.get("user_id"),
                        doc.get("leave_type"),
                        doc.get("start_date"),
                        doc.get("end_date"),
                        doc.get("half_day_period"),
                        doc.get("reason", ""),
                        doc.get("status", "pending"),
                        doc.get("admin_notes", ""),
                        doc.get("reviewed_by"),
                        doc.get("reviewed_at"),
                        doc.get("total_days", 0),
                        doc.get("created_at"),
                        doc.get("updated_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, request_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_COLUMNS)} FROM leave_requests WHERE request_id = %s',
                    (request_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                data = _norm_row(dict(zip(_COLUMNS, row)))
                data["id"] = request_id
                return data
        finally:
            conn.close()

    def list_requests(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        conditions: list[str] = []
        values: list = []

        if "user_id" in filters:
            conditions.append("user_id = %s")
            values.append(filters["user_id"])
        if "status" in filters:
            conditions.append("status = %s")
            values.append(filters["status"])

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_COLUMNS)} FROM leave_requests '
                    f'{where_clause} ORDER BY created_at DESC',
                    values,
                )
                results = []
                for row in cur.fetchall():
                    data = _norm_row(dict(zip(_COLUMNS, row)))
                    data["id"] = data["request_id"]
                    results.append(data)
                return results
        finally:
            conn.close()

    def find_overlapping(
        self, user_id: str, start_date: date, end_date: date
    ) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(_COLUMNS)} FROM leave_requests "
                    "WHERE user_id = %s AND status IN ('pending', 'approved') "
                    "AND start_date <= %s AND end_date >= %s LIMIT 1",
                    (user_id, end_date, start_date),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def update_review(
        self,
        request_id: str,
        status: str,
        admin_id: str,
        notes: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE leave_requests SET status = %s, admin_notes = %s, "
                    "reviewed_by = %s, reviewed_at = %s, updated_at = %s "
                    "WHERE request_id = %s",
                    (status, notes, admin_id, reviewed_at, updated_at, request_id),
                )
            conn.commit()
        finally:
            conn.close()

    def cancel(self, request_id: str, updated_at: datetime) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE leave_requests SET status = 'cancelled', updated_at = %s "
                    "WHERE request_id = %s",
                    (updated_at, request_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_approved_for_date(self, target_date: date) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(_COLUMNS)} FROM leave_requests "
                    "WHERE status = 'approved' AND start_date <= %s AND end_date >= %s",
                    (target_date, target_date),
                )
                results = []
                for row in cur.fetchall():
                    data = _norm_row(dict(zip(_COLUMNS, row)))
                    data["id"] = data["request_id"]
                    results.append(data)
                return results
        finally:
            conn.close()

    def count_pending(self) -> int:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM leave_requests WHERE status = 'pending'"
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_leave_repository() -> LeaveRepository:
    return PostgresLeaveRepository()
