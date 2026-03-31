"""PostgreSQL index management for high-traffic query paths."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from utils.db.postgres_client import get_postgres_connection


@dataclass(frozen=True)
class IndexSpec:
    name: str
    table: str
    definition: str


INDEX_SPECS: tuple[IndexSpec, ...] = (
    # Staff and auth lookups.
    IndexSpec("idx_staff_status_created_at", "staff", "(status, created_at DESC)"),
    IndexSpec("idx_admins_is_root_created_at", "admins", "(is_root, created_at DESC)"),

    # Attendance queries by user/date ranges and per-day dashboards.
    IndexSpec("idx_attendance_user_date", "attendance_logs", "(user_id, attendance_date)"),
    IndexSpec("idx_attendance_date_user", "attendance_logs", "(attendance_date, user_id)"),

    # Financial request filters, ordering, and IST date-range reports.
    IndexSpec("idx_financial_status_created_at", "financial_requests", "(status, created_at DESC)"),
    IndexSpec("idx_financial_user_status_created_at", "financial_requests", "(user_id, status, created_at DESC)"),
    IndexSpec("idx_financial_category_created_at", "financial_requests", "(category, created_at DESC)"),
    IndexSpec("idx_financial_status_category_created_at", "financial_requests", "(status, category, created_at DESC)"),
    IndexSpec(
        "idx_financial_reimbursement_queue",
        "financial_requests",
        "(reimbursement_status, created_at DESC) WHERE type = 'shop_expense' AND status = 'approved'",
    ),
    IndexSpec("idx_financial_ist_date", "financial_requests", "(((created_at AT TIME ZONE 'Asia/Kolkata')::date))"),
    IndexSpec(
        "idx_financial_user_type_approved_ist_date",
        "financial_requests",
        "(user_id, type, ((created_at AT TIME ZONE 'Asia/Kolkata')::date)) WHERE status = 'approved'",
    ),

    # Leave request filters, overlap checks, and approval counts.
    IndexSpec("idx_leave_status_created_at", "leave_requests", "(status, created_at DESC)"),
    IndexSpec("idx_leave_user_status_created_at", "leave_requests", "(user_id, status, created_at DESC)"),
    IndexSpec("idx_leave_status_type_created_at", "leave_requests", "(status, leave_type, created_at DESC)"),
    IndexSpec("idx_leave_user_status_dates", "leave_requests", "(user_id, status, start_date, end_date)"),
    IndexSpec(
        "idx_leave_approved_dates",
        "leave_requests",
        "(start_date, end_date) WHERE status = 'approved'",
    ),

    # Overtime queues and user-period reports.
    IndexSpec("idx_overtime_status_created_at", "overtime_records", "(status, created_at DESC)"),
    IndexSpec("idx_overtime_user_created_at", "overtime_records", "(user_id, created_at DESC)"),
    IndexSpec("idx_overtime_user_status_record_date", "overtime_records", "(user_id, status, record_date)"),

    # Settlement list/count/dedupe paths.
    IndexSpec("idx_settlements_user_week_end_desc", "settlements", "(user_id, week_end DESC)"),
    IndexSpec(
        "idx_settlements_user_period_created_desc",
        "settlements",
        "(user_id, week_start, week_end, created_at DESC, settlement_id DESC)",
    ),
    IndexSpec("idx_settlements_created_week_end_desc", "settlements", "(created_at DESC, week_end DESC)"),
    IndexSpec(
        "idx_settlements_week_end_user_period_created_desc",
        "settlements",
        "(week_end DESC, user_id, week_start, created_at DESC, settlement_id DESC)",
    ),

    # Staff profile support tables.
    IndexSpec("idx_staff_gallery_user_uploaded_at", "staff_work_gallery", "(user_id, uploaded_at DESC)"),
    IndexSpec("idx_staff_performance_user_created_at", "staff_performance_logs", "(user_id, created_at DESC)"),
)


def ensure_postgres_indexes(index_specs: Sequence[IndexSpec] = INDEX_SPECS) -> dict[str, list[str]]:
    """Create missing indexes for known hot query paths.

    Returns a dict with keys: created, skipped_missing_table, failed.
    """
    result: dict[str, list[str]] = {
        "created": [],
        "skipped_missing_table": [],
        "failed": [],
    }

    with get_postgres_connection() as conn:
        with conn.cursor() as cur:
            for spec in index_specs:
                cur.execute("SELECT to_regclass(%s)", (f"public.{spec.table}",))
                if cur.fetchone()[0] is None:
                    result["skipped_missing_table"].append(spec.name)
                    continue

                try:
                    cur.execute(
                        f"CREATE INDEX IF NOT EXISTS {spec.name} ON {spec.table} {spec.definition}"
                    )
                    result["created"].append(spec.name)
                except Exception:
                    result["failed"].append(spec.name)

        conn.commit()

    return result
