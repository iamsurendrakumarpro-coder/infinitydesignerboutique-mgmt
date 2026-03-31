"""Bulk requester profile lookup utilities for approval-oriented APIs."""
from __future__ import annotations

from typing import Iterable

from utils.db.postgres_client import get_postgres_connection


def build_requester_context_map(user_ids: Iterable[str]) -> dict[str, dict]:
    """Return a map of user_id -> lightweight requester profile context."""
    unique_ids = sorted({str(uid).strip() for uid in user_ids if uid})
    if not unique_ids:
        return {}

    context_map: dict[str, dict] = {}

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, full_name, phone_number, role, designation
                FROM staff
                WHERE user_id = ANY(%s)
                """,
                (unique_ids,),
            )
            for row in cur.fetchall():
                user_id, full_name, phone_number, role, designation = row
                context_map[str(user_id)] = {
                    "requester_name": full_name or "Unknown Staff",
                    "requester_phone": phone_number or "",
                    "requester_role": role or "staff",
                    "requester_designation": designation or "",
                }

            cur.execute(
                """
                SELECT user_id, full_name, phone_number, role
                FROM admins
                WHERE user_id = ANY(%s)
                """,
                (unique_ids,),
            )
            for row in cur.fetchall():
                user_id, full_name, phone_number, role = row
                # Prefer staff profile if a duplicate id ever exists across tables.
                if str(user_id) in context_map:
                    continue
                context_map[str(user_id)] = {
                    "requester_name": full_name or "Unknown User",
                    "requester_phone": phone_number or "",
                    "requester_role": role or "admin",
                    "requester_designation": "Admin",
                }
    finally:
        conn.close()

    return context_map
