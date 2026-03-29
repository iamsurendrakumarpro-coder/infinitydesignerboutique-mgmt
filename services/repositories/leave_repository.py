"""
services/repositories/leave_repository.py

Leave request persistence adapter – Firestore + Postgres behind
get_leave_repository().

Table: leave_requests
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
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreLeaveRepository(LeaveRepository):
    _COLLECTION = "leave_requests"

    def save(self, request_id: str, doc: dict) -> None:
        get_firestore().collection(self._COLLECTION).document(request_id).set(doc)

    def get_by_id(self, request_id: str) -> dict | None:
        doc = get_firestore().collection(self._COLLECTION).document(request_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def list_requests(self, filters: dict | None = None) -> list[dict]:
        db = get_firestore()
        query = db.collection(self._COLLECTION)
        filters = filters or {}
        if "user_id" in filters:
            query = query.where("user_id", "==", filters["user_id"])
        if "status" in filters:
            query = query.where("status", "==", filters["status"])
        results = []
        for d in query.stream():
            data = d.to_dict()
            data["id"] = d.id
            results.append(data)
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def find_overlapping(
        self, user_id: str, start_date: date, end_date: date
    ) -> dict | None:
        existing = (
            get_firestore().collection(self._COLLECTION)
            .where("user_id", "==", user_id)
            .where("status", "in", ["pending", "approved"])
            .stream()
        )
        for doc in existing:
            ex = doc.to_dict()
            try:
                ex_start = datetime.strptime(ex["start_date"], "%Y-%m-%d").date()
                ex_end = datetime.strptime(ex["end_date"], "%Y-%m-%d").date()
                if start_date <= ex_end and end_date >= ex_start:
                    return ex
            except (KeyError, ValueError):
                continue
        return None

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

    def cancel(self, request_id: str, updated_at: datetime) -> None:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # noqa: PLC0415
        get_firestore().collection(self._COLLECTION).document(request_id).update({
            "status": "cancelled",
            "updated_at": SERVER_TIMESTAMP,
        })

    def get_approved_for_date(self, target_date: date) -> list[dict]:
        date_str = target_date.isoformat()
        docs = (
            get_firestore().collection(self._COLLECTION)
            .where("status", "==", "approved")
            .where("start_date", "<=", date_str)
            .stream()
        )
        results = []
        for d in docs:
            data = d.to_dict()
            if data.get("end_date", "") >= date_str:
                data["id"] = d.id
                results.append(data)
        return results

    def count_pending(self) -> int:
        docs = list(
            get_firestore().collection(self._COLLECTION)
            .where("status", "==", "pending")
            .stream()
        )
        return len(docs)


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
    provider = os.environ.get("APP_DB_PROVIDER", "firebase").lower()
    if provider == "postgres":
        return PostgresLeaveRepository()
    return FirestoreLeaveRepository()
