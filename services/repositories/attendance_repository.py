"""Attendance persistence adapter for PostgreSQL."""
from __future__ import annotations

from datetime import date
from typing import Any

from utils.db.postgres_client import get_postgres_connection

class AttendanceRepository:
    """Persistence contract for attendance storage backends."""

    def get_by_user_and_date(self, user_id: str, day: date) -> dict | None:
        raise NotImplementedError

    def save(self, record: dict) -> None:
        raise NotImplementedError

    def list_by_user_between(self, user_id: str, start: date, end: date) -> list[dict]:
        raise NotImplementedError

    def list_by_date(self, day: date) -> list[dict]:
        raise NotImplementedError

    def list_by_users_between(self, user_ids: list[str], start: date, end: date) -> list[dict]:
        raise NotImplementedError


class PostgresAttendanceRepository(AttendanceRepository):
    _UPSERT_SQL = """
        INSERT INTO attendance_logs (
            record_id, user_id, attendance_date, punch_in, punch_out,
            status, duration_minutes, created_at, updated_at
        ) VALUES (
            %(record_id)s, %(user_id)s, %(attendance_date)s, %(punch_in)s, %(punch_out)s,
            %(status)s, %(duration_minutes)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (record_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            attendance_date = EXCLUDED.attendance_date,
            punch_in = EXCLUDED.punch_in,
            punch_out = EXCLUDED.punch_out,
            status = EXCLUDED.status,
            duration_minutes = EXCLUDED.duration_minutes,
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

    @staticmethod
    def _normalize(row: dict[str, Any] | None) -> dict | None:
        if row is None:
            return None
        out = dict(row)
        attendance_date = out.get("attendance_date")
        if isinstance(attendance_date, date):
            out["date"] = attendance_date.isoformat()
        else:
            out["date"] = str(attendance_date) if attendance_date else None
        out.pop("attendance_date", None)
        return out

    @staticmethod
    def _to_record_id(user_id: str, day: date | str) -> str:
        if isinstance(day, date):
            return day.strftime("%Y%m%d")
        return str(day).replace("-", "")

    def get_by_user_and_date(self, user_id: str, day: date) -> dict | None:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM attendance_logs
                    WHERE user_id = %s AND attendance_date = %s
                    LIMIT 1
                    """,
                    (user_id, day),
                )
                return self._normalize(self._fetchone_dict(cur))

    def save(self, record: dict) -> None:
        day_str = record.get("date")
        if isinstance(day_str, date):
            attendance_date = day_str
        else:
            attendance_date = date.fromisoformat(str(day_str))

        payload = {
            "record_id": record.get("record_id") or self._to_record_id(record["user_id"], attendance_date),
            "user_id": record["user_id"],
            "attendance_date": attendance_date,
            "punch_in": record.get("punch_in"),
            "punch_out": record.get("punch_out"),
            "status": record.get("status", "out"),
            "duration_minutes": int(record.get("duration_minutes", 0)),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        }

        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self._UPSERT_SQL, payload)
            conn.commit()

    def list_by_user_between(self, user_id: str, start: date, end: date) -> list[dict]:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM attendance_logs
                    WHERE user_id = %s
                      AND attendance_date >= %s
                      AND attendance_date <= %s
                    ORDER BY attendance_date ASC
                    """,
                    (user_id, start, end),
                )
                rows = self._fetchall_dicts(cur)
                return [self._normalize(r) for r in rows]

    def list_by_date(self, day: date) -> list[dict]:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM attendance_logs
                    WHERE attendance_date = %s
                    """,
                    (day,),
                )
                rows = self._fetchall_dicts(cur)
                return [self._normalize(r) for r in rows]

    def list_by_users_between(self, user_ids: list[str], start: date, end: date) -> list[dict]:
        if not user_ids:
            return []

        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM attendance_logs
                    WHERE user_id = ANY(%s)
                      AND attendance_date >= %s
                      AND attendance_date <= %s
                    ORDER BY user_id ASC, attendance_date ASC
                    """,
                    (user_ids, start, end),
                )
                rows = self._fetchall_dicts(cur)
                return [self._normalize(r) for r in rows]


def get_attendance_repository() -> AttendanceRepository:
    return PostgresAttendanceRepository()
