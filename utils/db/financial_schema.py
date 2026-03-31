"""Schema safety helpers for financial request reimbursement fields."""
from __future__ import annotations

from utils.db.postgres_client import get_postgres_connection


def ensure_financial_request_reimbursement_columns() -> dict[str, list[str]]:
    """Ensure reimbursement tracking columns exist on financial_requests.

    Returns a dict with created/skipped/failed for startup logging.
    """
    result: dict[str, list[str]] = {
        "created": [],
        "skipped": [],
        "failed": [],
    }

    table_check_sql = "SELECT to_regclass('public.financial_requests')"
    alter_statements = [
        (
            "reimbursement_status",
            "ALTER TABLE financial_requests ADD COLUMN IF NOT EXISTS reimbursement_status VARCHAR(32) NOT NULL DEFAULT 'pending'",
        ),
        (
            "reimbursed_by",
            "ALTER TABLE financial_requests ADD COLUMN IF NOT EXISTS reimbursed_by VARCHAR(64)",
        ),
        (
            "reimbursed_at",
            "ALTER TABLE financial_requests ADD COLUMN IF NOT EXISTS reimbursed_at TIMESTAMPTZ",
        ),
        (
            "reimbursement_notes",
            "ALTER TABLE financial_requests ADD COLUMN IF NOT EXISTS reimbursement_notes TEXT NOT NULL DEFAULT ''",
        ),
    ]

    with get_postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(table_check_sql)
            exists = cur.fetchone()[0] is not None
            if not exists:
                result["skipped"].append("financial_requests")
                conn.commit()
                return result

            for column_name, sql in alter_statements:
                try:
                    cur.execute(sql)
                    result["created"].append(column_name)
                except Exception:
                    result["failed"].append(column_name)

            # Keep personal advances out of reimbursement queues.
            try:
                cur.execute(
                    """
                    UPDATE financial_requests
                    SET reimbursement_status = 'not_applicable'
                    WHERE type = 'personal_advance'
                      AND COALESCE(reimbursement_status, '') <> 'not_applicable'
                    """
                )
            except Exception:
                result["failed"].append("backfill_not_applicable")

        conn.commit()

    return result
