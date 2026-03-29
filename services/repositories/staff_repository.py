"""
services/repositories/staff_repository.py

Staff persistence adapter – abstract interface + Firestore and Postgres
implementations.  Factory function get_staff_repository() selects the
provider at runtime based on APP_DB_PROVIDER env var.

Covers:
  - admins  collection (CRUD, phone uniqueness)
  - staff   collection (CRUD, status, skills, govt_proof)
  - staff/{uid}/work_gallery    subcollection / staff_work_gallery table
  - staff/{uid}/performance_logs subcollection / staff_performance_logs table
"""

from __future__ import annotations

import abc
import json
import os
from datetime import date, datetime
from decimal import Decimal

from utils.db.postgres_client import get_postgres_connection
from utils.firebase_client import get_firestore
from utils.timezone_utils import now_utc


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class StaffRepository(abc.ABC):

    # ---- Phone uniqueness ------------------------------------------------
    @abc.abstractmethod
    def is_phone_taken_admins(self, phone: str) -> bool: ...

    @abc.abstractmethod
    def is_phone_taken_staff(self, phone: str) -> bool: ...

    # ---- Admins ----------------------------------------------------------
    @abc.abstractmethod
    def save_admin(self, user_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def get_admin(self, user_id: str) -> dict | None: ...

    @abc.abstractmethod
    def list_admins(self, exclude_root: bool = True) -> list[dict]: ...

    # ---- Staff CRUD ------------------------------------------------------
    @abc.abstractmethod
    def save_staff(self, user_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def get_staff(self, user_id: str) -> dict | None: ...

    @abc.abstractmethod
    def list_staff(self, status_filter: str | None = None) -> list[dict]: ...

    @abc.abstractmethod
    def update_staff(self, user_id: str, fields: dict) -> None: ...

    @abc.abstractmethod
    def staff_exists(self, user_id: str) -> bool: ...

    # ---- Skills ----------------------------------------------------------
    @abc.abstractmethod
    def add_skill(self, user_id: str, skill: str, updated_at: datetime) -> None: ...

    @abc.abstractmethod
    def remove_skill(self, user_id: str, skill: str, updated_at: datetime) -> None: ...

    # ---- Work gallery ----------------------------------------------------
    @abc.abstractmethod
    def save_gallery_item(self, user_id: str, image_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def list_gallery(self, user_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_gallery_item(self, user_id: str, image_id: str) -> dict | None: ...

    @abc.abstractmethod
    def delete_gallery_item(self, user_id: str, image_id: str) -> None: ...

    # ---- Performance logs ------------------------------------------------
    @abc.abstractmethod
    def save_performance_log(self, user_id: str, log_id: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def list_performance_logs(self, user_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_performance_log(self, user_id: str, log_id: str) -> dict | None: ...

    @abc.abstractmethod
    def delete_performance_log(self, user_id: str, log_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

class FirestoreStaffRepository(StaffRepository):
    _ADMINS = "admins"
    _STAFF = "staff"

    # ---- Phone uniqueness ------------------------------------------------

    def is_phone_taken_admins(self, phone: str) -> bool:
        db = get_firestore()
        return bool(
            list(db.collection(self._ADMINS).where("phone_number", "==", phone).limit(1).stream())
        )

    def is_phone_taken_staff(self, phone: str) -> bool:
        db = get_firestore()
        return bool(
            list(db.collection(self._STAFF).where("phone_number", "==", phone).limit(1).stream())
        )

    # ---- Admins ----------------------------------------------------------

    def save_admin(self, user_id: str, doc: dict) -> None:
        get_firestore().collection(self._ADMINS).document(user_id).set(doc)

    def get_admin(self, user_id: str) -> dict | None:
        doc = get_firestore().collection(self._ADMINS).document(user_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data.pop("pin_hash", None)
        return data

    def list_admins(self, exclude_root: bool = True) -> list[dict]:
        db = get_firestore()
        query = db.collection(self._ADMINS)
        if exclude_root:
            query = query.where("is_root", "==", False)
        result = []
        for doc in query.stream():
            data = doc.to_dict()
            data.pop("pin_hash", None)
            result.append(data)
        return result

    # ---- Staff CRUD ------------------------------------------------------

    def save_staff(self, user_id: str, doc: dict) -> None:
        get_firestore().collection(self._STAFF).document(user_id).set(doc)

    def get_staff(self, user_id: str) -> dict | None:
        doc = get_firestore().collection(self._STAFF).document(user_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data.pop("pin_hash", None)
        return data

    def list_staff(self, status_filter: str | None = None) -> list[dict]:
        db = get_firestore()
        query = db.collection(self._STAFF)
        if status_filter:
            query = query.where("status", "==", status_filter)
        result = []
        for doc in query.stream():
            data = doc.to_dict()
            data.pop("pin_hash", None)
            result.append(data)
        return result

    def update_staff(self, user_id: str, fields: dict) -> None:
        get_firestore().collection(self._STAFF).document(user_id).update(fields)

    def staff_exists(self, user_id: str) -> bool:
        return get_firestore().collection(self._STAFF).document(user_id).get().exists

    # ---- Skills ----------------------------------------------------------

    def add_skill(self, user_id: str, skill: str, updated_at: datetime) -> None:
        from google.cloud.firestore_v1 import ArrayUnion, SERVER_TIMESTAMP  # noqa: PLC0415
        get_firestore().collection(self._STAFF).document(user_id).update(
            {"skills": ArrayUnion([skill]), "updated_at": SERVER_TIMESTAMP}
        )

    def remove_skill(self, user_id: str, skill: str, updated_at: datetime) -> None:
        from google.cloud.firestore_v1 import ArrayRemove, SERVER_TIMESTAMP  # noqa: PLC0415
        get_firestore().collection(self._STAFF).document(user_id).update(
            {"skills": ArrayRemove([skill]), "updated_at": SERVER_TIMESTAMP}
        )

    # ---- Work gallery ----------------------------------------------------

    def save_gallery_item(self, user_id: str, image_id: str, doc: dict) -> None:
        (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("work_gallery").document(image_id).set(doc)
        )

    def list_gallery(self, user_id: str) -> list[dict]:
        docs = (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("work_gallery")
            .order_by("uploaded_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]

    def get_gallery_item(self, user_id: str, image_id: str) -> dict | None:
        doc = (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("work_gallery").document(image_id).get()
        )
        return doc.to_dict() if doc.exists else None

    def delete_gallery_item(self, user_id: str, image_id: str) -> None:
        (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("work_gallery").document(image_id).delete()
        )

    # ---- Performance logs ------------------------------------------------

    def save_performance_log(self, user_id: str, log_id: str, doc: dict) -> None:
        (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("performance_logs").document(log_id).set(doc)
        )

    def list_performance_logs(self, user_id: str) -> list[dict]:
        docs = (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("performance_logs")
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [d.to_dict() for d in docs]

    def get_performance_log(self, user_id: str, log_id: str) -> dict | None:
        doc = (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("performance_logs").document(log_id).get()
        )
        return doc.to_dict() if doc.exists else None

    def delete_performance_log(self, user_id: str, log_id: str) -> None:
        (
            get_firestore().collection(self._STAFF).document(user_id)
            .collection("performance_logs").document(log_id).delete()
        )


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------

def _norm_row(row: dict) -> dict:
    """Normalise psycopg2 types for API parity (date/datetime → ISO, Decimal → float)."""
    result: dict = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, date):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    return result


# Columns returned for staff (excludes pin_hash)
_STAFF_COLUMNS = [
    "user_id", "full_name", "phone_number", "designation", "joining_date",
    "standard_login_time", "standard_logout_time", "emergency_contact",
    "salary_type", "settlement_cycle", "weekly_salary", "monthly_salary",
    "daily_salary", "skills", "status", "role", "is_first_login",
    "govt_proof", "created_by", "created_at", "updated_at",
]

# Columns returned for admins (excludes pin_hash)
_ADMIN_COLUMNS = [
    "user_id", "full_name", "phone_number", "role", "is_root",
    "is_first_login", "created_by", "created_at", "updated_at",
]

# Columns allowed in dynamic UPDATE for staff
_STAFF_UPDATE_ALLOWED = frozenset({
    "full_name", "designation", "joining_date", "standard_login_time",
    "standard_logout_time", "emergency_contact", "salary_type", "settlement_cycle",
    "weekly_salary", "monthly_salary", "daily_salary", "skills", "status",
    "is_first_login", "govt_proof", "updated_at",
})

_GALLERY_COLUMNS = [
    "image_id", "user_id", "image_url", "storage_path", "caption",
    "uploaded_by", "uploaded_at",
]

_PERF_LOG_COLUMNS = ["log_id", "user_id", "note", "created_by", "created_at"]


# ---------------------------------------------------------------------------
# Postgres implementation
# ---------------------------------------------------------------------------

class PostgresStaffRepository(StaffRepository):

    # ---- Phone uniqueness ------------------------------------------------

    def is_phone_taken_admins(self, phone: str) -> bool:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM admins WHERE phone_number = %s LIMIT 1", (phone,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    def is_phone_taken_staff(self, phone: str) -> bool:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM staff WHERE phone_number = %s LIMIT 1", (phone,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    # ---- Admins ----------------------------------------------------------

    def save_admin(self, user_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO admins
                        (user_id, full_name, phone_number, pin_hash, role,
                         is_root, is_first_login, created_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        full_name      = EXCLUDED.full_name,
                        pin_hash       = EXCLUDED.pin_hash,
                        is_first_login = EXCLUDED.is_first_login,
                        updated_at     = EXCLUDED.updated_at
                    """,
                    (
                        user_id,
                        doc.get("full_name"),
                        doc.get("phone_number"),
                        doc.get("pin_hash"),
                        doc.get("role", "admin"),
                        bool(doc.get("is_root", False)),
                        bool(doc.get("is_first_login", True)),
                        doc.get("created_by"),
                        doc.get("created_at"),
                        doc.get("updated_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_admin(self, user_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ", ".join(f'"{c}"' for c in _ADMIN_COLUMNS)
                cur.execute(
                    f'SELECT {placeholders} FROM admins WHERE user_id = %s',
                    (user_id,),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_ADMIN_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def list_admins(self, exclude_root: bool = True) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ", ".join(f'"{c}"' for c in _ADMIN_COLUMNS)
                if exclude_root:
                    cur.execute(f'SELECT {placeholders} FROM admins WHERE is_root = FALSE')
                else:
                    cur.execute(f'SELECT {placeholders} FROM admins')
                return [_norm_row(dict(zip(_ADMIN_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    # ---- Staff CRUD ------------------------------------------------------

    def save_staff(self, user_id: str, doc: dict) -> None:
        govt_proof_json = json.dumps(doc.get("govt_proof")) if doc.get("govt_proof") is not None else None
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staff
                        (user_id, full_name, phone_number, designation, joining_date,
                         standard_login_time, standard_logout_time, emergency_contact,
                         salary_type, settlement_cycle, weekly_salary, monthly_salary,
                         daily_salary, skills, status, pin_hash, role, is_first_login,
                         govt_proof, created_by, created_at, updated_at)
                    VALUES
                        (%s, %s, %s, %s, %s::date,
                         %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s, %s, %s, %s, %s,
                         %s::jsonb, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        full_name            = EXCLUDED.full_name,
                        designation          = EXCLUDED.designation,
                        joining_date         = EXCLUDED.joining_date,
                        standard_login_time  = EXCLUDED.standard_login_time,
                        standard_logout_time = EXCLUDED.standard_logout_time,
                        emergency_contact    = EXCLUDED.emergency_contact,
                        salary_type          = EXCLUDED.salary_type,
                        settlement_cycle     = EXCLUDED.settlement_cycle,
                        weekly_salary        = EXCLUDED.weekly_salary,
                        monthly_salary       = EXCLUDED.monthly_salary,
                        daily_salary         = EXCLUDED.daily_salary,
                        skills               = EXCLUDED.skills,
                        status               = EXCLUDED.status,
                        pin_hash             = EXCLUDED.pin_hash,
                        is_first_login       = EXCLUDED.is_first_login,
                        govt_proof           = EXCLUDED.govt_proof,
                        updated_at           = EXCLUDED.updated_at
                    """,
                    (
                        user_id,
                        doc.get("full_name"),
                        doc.get("phone_number"),
                        doc.get("designation"),
                        doc.get("joining_date") or None,
                        doc.get("standard_login_time"),
                        doc.get("standard_logout_time"),
                        doc.get("emergency_contact", ""),
                        doc.get("salary_type", "weekly"),
                        doc.get("settlement_cycle", "weekly"),
                        doc.get("weekly_salary"),
                        doc.get("monthly_salary"),
                        doc.get("daily_salary"),
                        doc.get("skills", []),
                        doc.get("status", "active"),
                        doc.get("pin_hash"),
                        doc.get("role", "staff"),
                        bool(doc.get("is_first_login", True)),
                        govt_proof_json,
                        doc.get("created_by"),
                        doc.get("created_at"),
                        doc.get("updated_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_staff(self, user_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ", ".join(f'"{c}"' for c in _STAFF_COLUMNS)
                cur.execute(
                    f'SELECT {placeholders} FROM staff WHERE user_id = %s',
                    (user_id,),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_STAFF_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def list_staff(self, status_filter: str | None = None) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                placeholders = ", ".join(f'"{c}"' for c in _STAFF_COLUMNS)
                if status_filter:
                    cur.execute(
                        f'SELECT {placeholders} FROM staff WHERE status = %s',
                        (status_filter,),
                    )
                else:
                    cur.execute(f'SELECT {placeholders} FROM staff')
                return [_norm_row(dict(zip(_STAFF_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def update_staff(self, user_id: str, fields: dict) -> None:
        safe = {k: v for k, v in fields.items() if k in _STAFF_UPDATE_ALLOWED}
        if not safe:
            return
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                set_parts: list[str] = []
                values: list = []
                for col, val in safe.items():
                    if col == "skills":
                        set_parts.append("skills = %s")
                        values.append(val if isinstance(val, list) else [])
                    elif col == "govt_proof":
                        set_parts.append("govt_proof = %s::jsonb")
                        values.append(json.dumps(val) if val is not None else None)
                    elif col == "joining_date" and isinstance(val, str):
                        set_parts.append("joining_date = %s::date")
                        values.append(val)
                    else:
                        set_parts.append(f'"{col}" = %s')
                        values.append(val)
                values.append(user_id)
                cur.execute(
                    f'UPDATE staff SET {", ".join(set_parts)} WHERE user_id = %s',
                    values,
                )
            conn.commit()
        finally:
            conn.close()

    def staff_exists(self, user_id: str) -> bool:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM staff WHERE user_id = %s LIMIT 1", (user_id,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    # ---- Skills ----------------------------------------------------------

    def add_skill(self, user_id: str, skill: str, updated_at: datetime) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE staff
                    SET skills = CASE WHEN %s = ANY(skills) THEN skills
                                      ELSE array_append(skills, %s) END,
                        updated_at = %s
                    WHERE user_id = %s
                    """,
                    (skill, skill, updated_at, user_id),
                )
            conn.commit()
        finally:
            conn.close()

    def remove_skill(self, user_id: str, skill: str, updated_at: datetime) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE staff SET skills = array_remove(skills, %s), updated_at = %s WHERE user_id = %s",
                    (skill, updated_at, user_id),
                )
            conn.commit()
        finally:
            conn.close()

    # ---- Work gallery ----------------------------------------------------

    def save_gallery_item(self, user_id: str, image_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staff_work_gallery
                        (image_id, user_id, image_url, storage_path, caption, uploaded_by, uploaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (image_id) DO UPDATE SET
                        image_url    = EXCLUDED.image_url,
                        storage_path = EXCLUDED.storage_path,
                        caption      = EXCLUDED.caption,
                        uploaded_by  = EXCLUDED.uploaded_by,
                        uploaded_at  = EXCLUDED.uploaded_at
                    """,
                    (
                        image_id,
                        user_id,
                        doc.get("image_url", ""),
                        doc.get("storage_path", ""),
                        doc.get("caption", ""),
                        doc.get("uploaded_by"),
                        doc.get("uploaded_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_gallery(self, user_id: str) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, user_id, image_url, storage_path, caption, uploaded_by, uploaded_at "
                    "FROM staff_work_gallery WHERE user_id = %s ORDER BY uploaded_at DESC",
                    (user_id,),
                )
                return [_norm_row(dict(zip(_GALLERY_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_gallery_item(self, user_id: str, image_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT image_id, user_id, image_url, storage_path, caption, uploaded_by, uploaded_at "
                    "FROM staff_work_gallery WHERE image_id = %s AND user_id = %s",
                    (image_id, user_id),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_GALLERY_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def delete_gallery_item(self, user_id: str, image_id: str) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM staff_work_gallery WHERE image_id = %s AND user_id = %s",
                    (image_id, user_id),
                )
            conn.commit()
        finally:
            conn.close()

    # ---- Performance logs ------------------------------------------------

    def save_performance_log(self, user_id: str, log_id: str, doc: dict) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staff_performance_logs (log_id, user_id, note, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (log_id) DO UPDATE SET
                        note       = EXCLUDED.note,
                        created_by = EXCLUDED.created_by,
                        created_at = EXCLUDED.created_at
                    """,
                    (
                        log_id,
                        user_id,
                        doc.get("note", ""),
                        doc.get("created_by"),
                        doc.get("created_at"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_performance_logs(self, user_id: str) -> list[dict]:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT log_id, user_id, note, created_by, created_at "
                    "FROM staff_performance_logs WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
                return [_norm_row(dict(zip(_PERF_LOG_COLUMNS, row))) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_performance_log(self, user_id: str, log_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT log_id, user_id, note, created_by, created_at "
                    "FROM staff_performance_logs WHERE log_id = %s AND user_id = %s",
                    (log_id, user_id),
                )
                row = cur.fetchone()
                return _norm_row(dict(zip(_PERF_LOG_COLUMNS, row))) if row else None
        finally:
            conn.close()

    def delete_performance_log(self, user_id: str, log_id: str) -> None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM staff_performance_logs WHERE log_id = %s AND user_id = %s",
                    (log_id, user_id),
                )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_staff_repository() -> StaffRepository:
    provider = os.environ.get("APP_DB_PROVIDER", "firebase").lower()
    if provider == "postgres":
        return PostgresStaffRepository()
    return FirestoreStaffRepository()
