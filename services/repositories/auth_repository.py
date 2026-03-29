"""
services/repositories/auth_repository.py

Authentication-specific persistence adapter – reads pin_hash (excluded from
staff/admin general reads) and handles PIN updates.

Covers: admins + staff tables, lookup by phone, lookup by user_id with hash,
PIN update.
"""

from __future__ import annotations

import abc
import os
from datetime import datetime

from utils.db.postgres_client import get_postgres_connection
from utils.firebase_client import get_firestore


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class AuthRepository(abc.ABC):

    @abc.abstractmethod
    def get_admin_by_phone(self, phone: str) -> dict | None:
        """Return full admin doc including pin_hash, or None."""
        ...

    @abc.abstractmethod
    def get_staff_by_phone(self, phone: str) -> dict | None:
        """Return full staff doc including pin_hash, or None."""
        ...

    @abc.abstractmethod
    def get_user_with_hash(self, role: str, user_id: str) -> dict | None:
        """Return doc including pin_hash for the given role/user_id, or None."""
        ...

    @abc.abstractmethod
    def update_pin(
        self,
        role: str,
        user_id: str,
        pin_hash: str,
        is_first_login: bool,
        updated_at: datetime,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Firestore implementation
# ---------------------------------------------------------------------------

_ADMINS = "admins"
_STAFF = "staff"


class FirestoreAuthRepository(AuthRepository):

    def get_admin_by_phone(self, phone: str) -> dict | None:
        docs = list(
            get_firestore().collection(_ADMINS)
            .where("phone_number", "==", phone)
            .limit(1)
            .stream()
        )
        return docs[0].to_dict() if docs else None

    def get_staff_by_phone(self, phone: str) -> dict | None:
        docs = list(
            get_firestore().collection(_STAFF)
            .where("phone_number", "==", phone)
            .limit(1)
            .stream()
        )
        return docs[0].to_dict() if docs else None

    def get_user_with_hash(self, role: str, user_id: str) -> dict | None:
        collection = _ADMINS if role == "admin" else _STAFF
        doc = get_firestore().collection(collection).document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def update_pin(
        self,
        role: str,
        user_id: str,
        pin_hash: str,
        is_first_login: bool,
        updated_at: datetime,
    ) -> None:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP  # noqa: PLC0415
        collection = _ADMINS if role == "admin" else _STAFF
        get_firestore().collection(collection).document(user_id).update({
            "pin_hash": pin_hash,
            "is_first_login": is_first_login,
            "updated_at": SERVER_TIMESTAMP,
        })


# ---------------------------------------------------------------------------
# Postgres implementation
# ---------------------------------------------------------------------------

_ADMIN_COLUMNS_WITH_HASH = [
    "user_id", "full_name", "phone_number", "pin_hash", "role",
    "is_root", "is_first_login", "created_by", "created_at", "updated_at",
]

_STAFF_COLUMNS_WITH_HASH = [
    "user_id", "full_name", "phone_number", "pin_hash", "role",
    "is_first_login", "status", "designation",
]


class PostgresAuthRepository(AuthRepository):

    def get_admin_by_phone(self, phone: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cols = ", ".join(_ADMIN_COLUMNS_WITH_HASH)
                cur.execute(
                    f"SELECT {cols} FROM admins WHERE phone_number = %s LIMIT 1",
                    (phone,),
                )
                row = cur.fetchone()
                return dict(zip(_ADMIN_COLUMNS_WITH_HASH, row)) if row else None
        finally:
            conn.close()

    def get_staff_by_phone(self, phone: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cols = ", ".join(_STAFF_COLUMNS_WITH_HASH)
                cur.execute(
                    f"SELECT {cols} FROM staff WHERE phone_number = %s LIMIT 1",
                    (phone,),
                )
                row = cur.fetchone()
                return dict(zip(_STAFF_COLUMNS_WITH_HASH, row)) if row else None
        finally:
            conn.close()

    def get_user_with_hash(self, role: str, user_id: str) -> dict | None:
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                if role == "admin":
                    cols = ", ".join(_ADMIN_COLUMNS_WITH_HASH)
                    cur.execute(
                        f"SELECT {cols} FROM admins WHERE user_id = %s LIMIT 1",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(zip(_ADMIN_COLUMNS_WITH_HASH, row)) if row else None
                else:
                    cols = ", ".join(_STAFF_COLUMNS_WITH_HASH)
                    cur.execute(
                        f"SELECT {cols} FROM staff WHERE user_id = %s LIMIT 1",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(zip(_STAFF_COLUMNS_WITH_HASH, row)) if row else None
        finally:
            conn.close()

    def update_pin(
        self,
        role: str,
        user_id: str,
        pin_hash: str,
        is_first_login: bool,
        updated_at: datetime,
    ) -> None:
        table = "admins" if role == "admin" else "staff"
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {table} SET pin_hash = %s, is_first_login = %s, "
                    "updated_at = %s WHERE user_id = %s",
                    (pin_hash, is_first_login, updated_at, user_id),
                )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_auth_repository() -> AuthRepository:
    provider = os.environ.get("APP_DB_PROVIDER", "firebase").lower()
    if provider == "postgres":
        return PostgresAuthRepository()
    return FirestoreAuthRepository()
