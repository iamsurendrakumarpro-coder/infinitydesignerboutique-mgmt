#!/usr/bin/env python3
"""Quick performance benchmark for dashboard and settlement list paths."""
from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from services.repositories.attendance_repository import get_attendance_repository
from services.repositories.settlement_repository import get_settlement_repository
from services import dashboard_service
from services.user_service import list_staff
from utils.timezone_utils import today_ist


def time_call(fn, repeat: int = 1):
    samples = []
    result = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        end = time.perf_counter()
        samples.append(end - start)
    return {
        "mean_ms": round(statistics.mean(samples) * 1000, 2),
        "min_ms": round(min(samples) * 1000, 2),
        "max_ms": round(max(samples) * 1000, 2),
        "samples_ms": [round(s * 1000, 2) for s in samples],
        "result": result,
    }


def benchmark_dashboard_repo_paths() -> dict:
    repo = get_attendance_repository()
    active_staff = list_staff(status_filter="active")
    active_ids = [s.get("user_id") for s in active_staff if s.get("user_id")]
    old_sample_ids = active_ids[:10]
    today = today_ist()

    def old_daily_summary_style():
        found = 0
        for sid in old_sample_ids:
            if repo.get_by_user_and_date(sid, today):
                found += 1
        return found

    def new_daily_summary_style():
        rows = repo.list_by_date(today)
        attendance_by_user = {r.get("user_id"): r for r in rows if r.get("user_id")}
        found = 0
        for sid in active_ids:
            if sid in attendance_by_user:
                found += 1
        return found

    trend_start = today - timedelta(days=6)

    def old_trend_style():
        count = 0
        for offset in range(7):
            day = trend_start + timedelta(days=offset)
            for sid in old_sample_ids:
                if repo.get_by_user_and_date(sid, day):
                    count += 1
        return count

    def new_trend_style():
        rows = repo.list_by_users_between(active_ids, trend_start, today)
        return len(rows)

    old_daily = time_call(old_daily_summary_style)
    new_daily = time_call(new_daily_summary_style)
    old_trend = time_call(old_trend_style)
    new_trend = time_call(new_trend_style)

    return {
        "active_staff_count": len(active_ids),
        "old_path_sample_staff_count": len(old_sample_ids),
        "daily_summary": {
            "old_ms": old_daily["mean_ms"],
            "new_ms": new_daily["mean_ms"],
            "speedup_x": round(old_daily["mean_ms"] / max(new_daily["mean_ms"], 0.01), 2),
            "note": "Old path measured on sample set; new path measured on full active staff.",
        },
        "attendance_trend_7d": {
            "old_ms": old_trend["mean_ms"],
            "new_ms": new_trend["mean_ms"],
            "speedup_x": round(old_trend["mean_ms"] / max(new_trend["mean_ms"], 0.01), 2),
            "rows_old_sample_logic": old_trend["result"],
            "rows_new_full_logic": new_trend["result"],
            "note": "Old path measured on sample set; new path measured on full active staff.",
        },
    }


def benchmark_settlement_repo_paths() -> dict:
    repo = get_settlement_repository()

    def old_style_list_dedupe():
        # Simulate the old path: fetch all rows then dedupe in Python.
        rows = repo._query_many(
            "SELECT * FROM settlements ORDER BY created_at DESC NULLS LAST, week_end DESC",
            tuple(),
        )
        deduped = {}
        for row in rows:
            key = (row.get("user_id"), row.get("week_start"), row.get("week_end"))
            created = str(row.get("created_at", ""))
            if key not in deduped or created > str(deduped[key].get("created_at", "")):
                deduped[key] = row
        return len(deduped)

    def new_style_db_dedupe_page():
        rows = repo.list_settlements(limit=100, offset=0)
        return len(rows)

    old_list = time_call(old_style_list_dedupe)
    new_list = time_call(new_style_db_dedupe_page)

    return {
        "settlement_list": {
            "old_ms": old_list["mean_ms"],
            "new_ms": new_list["mean_ms"],
            "speedup_x": round(old_list["mean_ms"] / max(new_list["mean_ms"], 0.01), 2),
            "rows_old_deduped": old_list["result"],
            "rows_new_page": new_list["result"],
        }
    }


def benchmark_dashboard_service_calls() -> dict:
    today = today_ist()
    start = today - timedelta(days=6)

    summary = time_call(lambda: dashboard_service.get_daily_summary(today))
    analytics = time_call(lambda: dashboard_service.get_dashboard_analytics())
    attendance_summary = time_call(lambda: dashboard_service.get_attendance_summary(start, today))

    return {
        "get_daily_summary_ms": summary["mean_ms"],
        "get_dashboard_analytics_ms": analytics["mean_ms"],
        "get_attendance_summary_7d_ms": attendance_summary["mean_ms"],
    }


def benchmark_live_endpoints() -> dict:
    app = create_app()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user_id"] = "seed-admin-vijay-sharma"
        sess["role"] = "admin"
        sess["is_first_login"] = False
        sess["full_name"] = "Vijay Sharma"
        sess["phone_number"] = "9876543210"

    endpoints = [
        "/api/dashboard/summary",
        "/api/dashboard/analytics",
        "/api/settlements?page=1&page_size=100",
    ]

    report = {}
    for ep in endpoints:
        def call_endpoint():
            res = client.get(ep)
            return res.status_code

        timing = time_call(call_endpoint)
        report[ep] = {
            "mean_ms": timing["mean_ms"],
            "min_ms": timing["min_ms"],
            "max_ms": timing["max_ms"],
            "status_code": timing["result"],
        }

    return report


def main() -> None:
    output = {
        "dashboard_repo_before_after": benchmark_dashboard_repo_paths(),
        "settlement_repo_before_after": benchmark_settlement_repo_paths(),
        "dashboard_service_timings": benchmark_dashboard_service_calls(),
        "endpoint_timings": benchmark_live_endpoints(),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
