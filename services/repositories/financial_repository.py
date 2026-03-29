"""
services/repositories/financial_repository.py

Financial request persistence adapter – Firestore + Postgres behind
get_financial_repository().

Table: financial_requests
"""

from __future__ import annotations

import abc
import os
from datetime import date, datetime
from decimal import Decimal

from utils.db.postgres_client import get_postgres_connection
from utils.firebase_client import get_firestore
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


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreFinancialRepository(FinancialRepository):
    _COLLECTION = "financial_requests"

    def save(self, request_id: str, doc: dict) -> None:
        get_firestore().collection(self._COLLECTION).document(request_id).set(doc)

    def get_by_id(self, request_id: str) -> dict | None:
        doc = get_firestore().collection(self._COLLECTION).document(request_id).get()
        return doc.to_dict() if doc.exists else None

    def list_requests(self, filters: dict | None = None) -> list[dict]:
        db = get_firestore()
        query = db.collection(self._COLLECTION)
        filters = filters or {}
        if filters.get("status"):
            query = query.where("status", "==", filters["status"])
        if filters.get("user_id"):
            query = query.where("user_id", "==", filters["user_id"])
        if filters.get("category"):
            query = query.where("category", "==", filters["category"])
        if filters.get("start_date"):
            query = query.where("created_at", ">=", filters["start_date"])
        if filters.get("end_date"):
            query = query.where("created_at", "<=", filters["end_date"])
        query = query.order_by("created_at", direction="DESCENDING")
        return [d.to_dict() for d in query.stream()]

    def update_review(
        self,
        request_id: str,
        status: str,
        admin_id: str,
        notes: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # noqa: PLC0415
        get_firestore().collection(self._COLLECTION).document(request_id).update({
            "status": status,
            "admin_notes": notes,
            "reviewed_by": admin_id,
            "reviewed_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })

    def get_approved_for_period(
        self,
        user_id: str,
        start: date,
        end: date,
        req_type: str | None = None,
    ) -> list[dict]:
        import pytz  # noqa: PLC0415
        IST = pytz.timezone("Asia/Kolkata")
        start_dt = IST.localize(datetime.combine(start, datetime.min.time()))
        end_dt = IST.localize(datetime.combine(end, datetime.max.time()))

        db = get_firestore()
        query = (
            db.collection(self._COLLECTION)
            .where("user_id", "==", user_id)
            .where("status", "==", "approved")
        )
        results = []
        for d in query.stream():
            data = d.to_dict()
            created = data.get("created_at")
            if created and hasattr(created, "date"):
                doc_date = (
                    created.date() if not hasattr(created, "astimezone")
                    else created.astimezone(IST).date()
                )
                if start <= doc_date <= end:
                    if req_type is None or data.get("type") == req_type:
                        results.append(data)
        return results

    def request_exists(self, request_id: str) -> dict | None:
        doc = get_firestore().collection(self._COLLECTION).document(request_id).get()
        return doc.to_dict() if doc.exists else None


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
                         created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        status         = EXCLUDED.status,
                        admin_notes    = EXCLUDED.admin_notes,
                        reviewed_by    = EXCLUDED.reviewed_by,
                        reviewed_at    = EXCLUDED.reviewed_at,
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


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_financial_repository() -> FinancialRepository:
    provider = os.environ.get("APP_DB_PROVIDER", "firebase").lower()
    if provider == "postgres":
        return PostgresFinancialRepository()
    return FirestoreFinancialRepository()
