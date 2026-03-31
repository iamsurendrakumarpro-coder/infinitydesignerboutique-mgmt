"""
services/repositories/financial_repository.py

Financial request persistence adapter for PostgreSQL.

Table: financial_requests
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
    """Normalise psycopg2 types: Decimal → float, date → ISO string.
    Datetime objects are LEFT as Python datetime so that _sanitise() in the
    service can call format_ist() and produce IST-formatted strings.
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
    "request_id", "user_id", "type", "category", "amount",
    "receipt_gcs_path", "notes", "status", "admin_notes",
    "reviewed_by", "reviewed_at", "created_at", "updated_at",
    "reimbursement_status", "reimbursed_by", "reimbursed_at", "reimbursement_notes",
]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class FinancialRepository(abc.ABC):

    @abc.abstractmethod
    def save(self, request_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def get_by_id(self, request_id: str) -> dict | None: ...

    @abc.abstractmethod
    def list_requests(self, filters: dict | None = None) -> list[dict]: ...

    @abc.abstractmethod
    def count_requests(self, filters: dict | None = None) -> int: ...

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
    def get_approved_for_period(
        self,
        user_id: str,
        start: date,
        end: date,
        req_type: str | None = None,
    ) -> list[dict]: ...

    @abc.abstractmethod
    def request_exists(self, request_id: str) -> dict | None:
        """Return raw doc dict (with status) or None."""
        ...

    @abc.abstractmethod
    def update_reimbursement(
        self,
        request_id: str,
        reimbursement_status: str,
        reimbursed_by: str,
        reimbursement_notes: str,
        reimbursed_at: datetime,
        updated_at: datetime,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Postgres implementation
# ---------------------------------------------------------------------------

class PostgresFinancialRepository(FinancialRepository):

    def save(self, request_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO financial_requests
                        (request_id, user_id, type, category, amount, receipt_gcs_path,
                         notes, status, admin_notes, reviewed_by, reviewed_at,
                         created_at, updated_at, reimbursement_status, reimbursed_by,
                         reimbursed_at, reimbursement_notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        status         = EXCLUDED.status,
                        admin_notes    = EXCLUDED.admin_notes,
                        reviewed_by    = EXCLUDED.reviewed_by,
                        reviewed_at    = EXCLUDED.reviewed_at,
                        reimbursement_status = EXCLUDED.reimbursement_status,
                        reimbursed_by  = EXCLUDED.reimbursed_by,
                        reimbursed_at  = EXCLUDED.reimbursed_at,
                        reimbursement_notes = EXCLUDED.reimbursement_notes,
                        updated_at     = EXCLUDED.updated_at
                    """,
                    (
                        request_id,
                        doc.get("user_id"),
                        doc.get("type"),
                        doc.get("category", ""),
                        doc.get("amount"),
                        doc.get("receipt_gcs_path", ""),
                        doc.get("notes", ""),
                        doc.get("status", "pending"),
                        doc.get("admin_notes", ""),
                        doc.get("reviewed_by"),
                        doc.get("reviewed_at"),
                        doc.get("created_at"),
                        doc.get("updated_at"),
                        doc.get("reimbursement_status", "pending"),
                        doc.get("reimbursed_by"),
                        doc.get("reimbursed_at"),
                        doc.get("reimbursement_notes", ""),
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
                    f'SELECT {", ".join(_COLUMNS)} FROM financial_requests WHERE request_id = %s',
                    (request_id,),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def list_requests(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        conditions: list[str] = []
        values: list = []

        if filters.get("status"):
            conditions.append("status = %s")
            values.append(filters["status"])
        if filters.get("user_id"):
            conditions.append("user_id = %s")
            values.append(filters["user_id"])
        if filters.get("category"):
            conditions.append("category = %s")
            values.append(filters["category"])
        if filters.get("type"):
            conditions.append("type = %s")
            values.append(filters["type"])
        if filters.get("reimbursement_status"):
            conditions.append("reimbursement_status = %s")
            values.append(filters["reimbursement_status"])
        if filters.get("start_date"):
            conditions.append("(created_at AT TIME ZONE 'Asia/Kolkata')::date >= %s")
            values.append(filters["start_date"])
        if filters.get("end_date"):
            conditions.append("(created_at AT TIME ZONE 'Asia/Kolkata')::date <= %s")
            values.append(filters["end_date"])

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_COLUMNS)} FROM financial_requests '
                    f'{where_clause} ORDER BY created_at DESC',
                    values,
                )
                return [_norm_row(dict(zip(_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def count_requests(self, filters: dict | None = None) -> int:
        filters = filters or {}
        conditions: list[str] = []
        values: list = []

        if filters.get("status"):
            conditions.append("status = %s")
            values.append(filters["status"])
        if filters.get("user_id"):
            conditions.append("user_id = %s")
            values.append(filters["user_id"])
        if filters.get("category"):
            conditions.append("category = %s")
            values.append(filters["category"])
        if filters.get("type"):
            conditions.append("type = %s")
            values.append(filters["type"])
        if filters.get("reimbursement_status"):
            conditions.append("reimbursement_status = %s")
            values.append(filters["reimbursement_status"])
        if filters.get("start_date"):
            conditions.append("(created_at AT TIME ZONE 'Asia/Kolkata')::date >= %s")
            values.append(filters["start_date"])
        if filters.get("end_date"):
            conditions.append("(created_at AT TIME ZONE 'Asia/Kolkata')::date <= %s")
            values.append(filters["end_date"])

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) FROM financial_requests {where_clause}',
                    values,
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
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
                    """
                    UPDATE financial_requests
                    SET status = %s, admin_notes = %s, reviewed_by = %s,
                        reviewed_at = %s, updated_at = %s
                    WHERE request_id = %s
                    """,
                    (status, notes, admin_id, reviewed_at, updated_at, request_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_approved_for_period(
        self,
        user_id: str,
        start: date,
        end: date,
        req_type: str | None = None,
    ) -> list[dict]:
        conditions = [
            "user_id = %s",
            "status = 'approved'",
            "(created_at AT TIME ZONE 'Asia/Kolkata')::date >= %s",
            "(created_at AT TIME ZONE 'Asia/Kolkata')::date <= %s",
        ]
        values: list = [user_id, start, end]
        if req_type:
            conditions.append("type = %s")
            values.append(req_type)

        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_COLUMNS)} FROM financial_requests '
                    f'WHERE {" AND ".join(conditions)}',
                    values,
                )
                return [_norm_row(dict(zip(_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def request_exists(self, request_id: str) -> dict | None:
        return self.get_by_id(request_id)

    def update_reimbursement(
        self,
        request_id: str,
        reimbursement_status: str,
        reimbursed_by: str,
        reimbursement_notes: str,
        reimbursed_at: datetime,
        updated_at: datetime,
    ) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE financial_requests
                    SET reimbursement_status = %s,
                        reimbursed_by = %s,
                        reimbursement_notes = %s,
                        reimbursed_at = %s,
                        updated_at = %s
                    WHERE request_id = %s
                    """,
                    (
                        reimbursement_status,
                        reimbursed_by,
                        reimbursement_notes,
                        reimbursed_at,
                        updated_at,
                        request_id,
                    ),
                )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_financial_repository() -> FinancialRepository:
    return PostgresFinancialRepository()
