"""
services/repositories/overtime_repository.py

Overtime record persistence adapter – Firestore + Postgres behind
get_overtime_repository().

Table: overtime_records
Note: Firestore stores attendance date as "date" key (string).
      Postgres stores it as "record_date" column (DATE).
      The repository normalises to "date" key for API parity.
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
    """Normalize types: Decimal → float, date → ISO string.
    Datetimes are left as Python objects so _sanitise() in service can format them.
    Also normalises `record_date` → `date` for API parity with Firestore.
    """
    result: dict = {}
    for k, v in row.items():
        if isinstance(v, date) and not isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    # Rename record_date → date for API parity
    if "record_date" in result:
        result["date"] = result.pop("record_date")
    return result


_DB_COLUMNS = [
    "record_id", "user_id", "staff_name", "full_name", "record_date",
    "total_worked_minutes", "overtime_minutes", "hourly_rate",
    "calculated_payout", "status", "reviewed_by", "reviewed_at",
    "created_at", "updated_at",
]


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class OvertimeRepository(abc.ABC):

    @abc.abstractmethod
    def save(self, record_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def get_by_id(self, record_id: str) -> dict | None: ...

    @abc.abstractmethod
    def list_pending(self) -> list[dict]: ...

    @abc.abstractmethod
    def list_for_user(self, user_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def update_review(
        self,
        record_id: str,
        status: str,
        admin_id: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None: ...

    @abc.abstractmethod
    def get_approved_for_period(
        self, user_id: str, start: date, end: date
    ) -> list[dict]: ...

    @abc.abstractmethod
    def record_exists(self, record_id: str) -> dict | None:
        """Return raw doc (with status) or None."""
        ...


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreOvertimeRepository(OvertimeRepository):
    _COLLECTION = "overtime_records"

    def save(self, record_id: str, doc: dict) -> None:
        get_firestore().collection(self._COLLECTION).document(record_id).set(doc)

    def get_by_id(self, record_id: str) -> dict | None:
        doc = get_firestore().collection(self._COLLECTION).document(record_id).get()
        return doc.to_dict() if doc.exists else None

    def list_pending(self) -> list[dict]:
        docs = (
            get_firestore().collection(self._COLLECTION)
            .where("status", "==", "pending")
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]

    def list_for_user(self, user_id: str) -> list[dict]:
        docs = (
            get_firestore().collection(self._COLLECTION)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]

    def update_review(
        self,
        record_id: str,
        status: str,
        admin_id: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # noqa: PLC0415
        get_firestore().collection(self._COLLECTION).document(record_id).update({
            "status": status,
            "reviewed_by": admin_id,
            "reviewed_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        })

    def get_approved_for_period(
        self, user_id: str, start: date, end: date
    ) -> list[dict]:
        docs = (
            get_firestore().collection(self._COLLECTION)
            .where("user_id", "==", user_id)
            .where("status", "==", "approved")
            .stream()
        )
        results = []
        for d in docs:
            data = d.to_dict()
            record_date_str = data.get("date", "")
            if record_date_str:
                try:
                    record_date = datetime.strptime(record_date_str, "%Y-%m-%d").date()
                    if start <= record_date <= end:
                        results.append(data)
                except (ValueError, TypeError):
                    pass
        return results

    def record_exists(self, record_id: str) -> dict | None:
        doc = get_firestore().collection(self._COLLECTION).document(record_id).get()
        return doc.to_dict() if doc.exists else None


# ---------------------------------------------------------------------------
# Postgres implementation
# ---------------------------------------------------------------------------

class PostgresOvertimeRepository(OvertimeRepository):

    def save(self, record_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO overtime_records
                        (record_id, user_id, staff_name, full_name, record_date,
                         total_worked_minutes, overtime_minutes, hourly_rate,
                         calculated_payout, status, reviewed_by, reviewed_at,
                         created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (record_id) DO UPDATE SET
                        status       = EXCLUDED.status,
                        reviewed_by  = EXCLUDED.reviewed_by,
                        reviewed_at  = EXCLUDED.reviewed_at,
                        updated_at   = EXCLUDED.updated_at
                    """,
                    (
                        record_id,
                        doc.get("user_id"),
                        doc.get("staff_name", ""),
                        doc.get("full_name", ""),
                        doc.get("date") or None,  # "date" key from service
                        doc.get("total_worked_minutes", 0),
                        doc.get("overtime_minutes", 0),
                        doc.get("hourly_rate", 0),
                        doc.get("calculated_payout", 0),
                        doc.get("status", "pending"),
                        doc.get("reviewed_by"),
                        doc.get("reviewed_at"),
                        doc.get("created_at"),
                        doc.get("updated_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, record_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_DB_COLUMNS)} FROM overtime_records WHERE record_id = %s',
                    (record_id,),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_DB_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def list_pending(self) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_DB_COLUMNS)} FROM overtime_records '
                    "WHERE status = 'pending' ORDER BY created_at DESC"
                )
                return [_norm_row(dict(zip(_DB_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def list_for_user(self, user_id: str) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_DB_COLUMNS)} FROM overtime_records '
                    "WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
                return [_norm_row(dict(zip(_DB_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def update_review(
        self,
        record_id: str,
        status: str,
        admin_id: str,
        reviewed_at: datetime,
        updated_at: datetime,
    ) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE overtime_records SET status = %s, reviewed_by = %s, "
                    "reviewed_at = %s, updated_at = %s WHERE record_id = %s",
                    (status, admin_id, reviewed_at, updated_at, record_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_approved_for_period(
        self, user_id: str, start: date, end: date
    ) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT {", ".join(_DB_COLUMNS)} FROM overtime_records '
                    "WHERE user_id = %s AND status = 'approved' "
                    "AND record_date BETWEEN %s AND %s",
                    (user_id, start, end),
                )
                return [_norm_row(dict(zip(_DB_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def record_exists(self, record_id: str) -> dict | None:
        return self.get_by_id(record_id)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_overtime_repository() -> OvertimeRepository:
    provider = os.environ.get("APP_DB_PROVIDER", "firebase").lower()
    if provider == "postgres":
        return PostgresOvertimeRepository()
    return FirestoreOvertimeRepository()
