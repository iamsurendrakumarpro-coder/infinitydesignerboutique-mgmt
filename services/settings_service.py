"""
services/settings_service.py - Application settings management.

Settings are stored in PostgreSQL table app_settings:
  app_settings(config_type TEXT PRIMARY KEY, config JSONB, updated_by TEXT, updated_at TIMESTAMPTZ)

Settings are cached in memory with a TTL to reduce DB reads.
"""
from __future__ import annotations

import json
import time

from utils.db.postgres_client import get_postgres_connection
from utils.logger import get_logger, audit_log
from utils.timezone_utils import now_utc

log = get_logger(__name__)

_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


_DEFAULTS = {
    "app_config": {
        "boutique_name": "Infinity Designer Boutique",
        "timezone": "Asia/Kolkata",
        "default_login_time": "10:00",
        "default_logout_time": "19:00",
        "standard_hours_per_day": 8,
        "overtime_grace_minutes": 30,
        "working_days_per_week": 6,
    },
    "designations": {
        "list": [
            "cutting_master",
            "tailor",
            "embroidery_artist",
            "handwork_expert",
            "designer",
            "helper",
        ],
        "labels": {
            "cutting_master": "Cutting Master",
            "tailor": "Tailor",
            "embroidery_artist": "Embroidery Artist",
            "handwork_expert": "Handwork Expert",
            "designer": "Designer",
            "helper": "Helper",
        },
    },
    "staff_statuses": {
        "list": ["active", "inactive", "deactivated"],
    },
    "salary_config": {
        "salary_types": ["weekly"],
        "settlement_cycles": ["weekly"],
    },
}


def _load_from_db(config_type: str) -> dict | None:
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT config FROM app_settings WHERE config_type = %s LIMIT 1",
                (config_type,),
            )
            row = cur.fetchone()
            if not row:
                return None
            value = row[0]
            return value if isinstance(value, dict) else None
    finally:
        conn.close()


def get_settings(config_type: str, use_cache: bool = True) -> dict:
    if use_cache and config_type in _CACHE:
        data, timestamp = _CACHE[config_type]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            log.debug("get_settings | config_type=%s | source=cache", config_type)
            return data

    try:
        data = _load_from_db(config_type)
        if data is not None:
            log.debug("get_settings | config_type=%s | source=postgres", config_type)
        else:
            data = _DEFAULTS.get(config_type, {})
            log.info("get_settings | config_type=%s | source=defaults (row not found)", config_type)
    except Exception as exc:  # noqa: BLE001
        log.error("get_settings failed | config_type=%s | error=%s", config_type, exc)
        data = _DEFAULTS.get(config_type, {})

    _CACHE[config_type] = (data, time.time())
    return data


def update_settings(config_type: str, data: dict, updated_by: str) -> tuple[bool, str]:
    if config_type not in _DEFAULTS:
        return False, f"Invalid config type: {config_type}"

    try:
        existing_data = get_settings(config_type, use_cache=False)
        merged = {**existing_data, **data}

        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_settings (config_type, config, updated_by, updated_at)
                    VALUES (%s, %s::jsonb, %s, %s)
                    ON CONFLICT (config_type) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (config_type, json.dumps(merged), updated_by, now_utc()),
                )
            conn.commit()
        finally:
            conn.close()

        invalidate_cache(config_type)
        log.info(
            "Settings updated | config_type=%s | by=%s | fields=%s",
            config_type,
            updated_by,
            list(data.keys()),
        )
        audit_log(updated_by, "UPDATE_SETTINGS", f"app_settings/{config_type}")
        return True, ""
    except Exception as exc:  # noqa: BLE001
        log.error("update_settings failed | config_type=%s | error=%s", config_type, exc)
        return False, str(exc)


def invalidate_cache(config_type: str | None = None) -> None:
    global _CACHE
    if config_type:
        _CACHE.pop(config_type, None)
        log.debug("Cache invalidated | config_type=%s", config_type)
    else:
        _CACHE = {}
        log.debug("Cache invalidated | all")


def get_all_settings() -> dict[str, dict]:
    return {
        "app_config": get_settings("app_config"),
        "designations": get_settings("designations"),
        "staff_statuses": get_settings("staff_statuses"),
        "salary_config": get_settings("salary_config"),
    }


def get_designations() -> tuple[list[str], dict[str, str]]:
    settings = get_settings("designations")
    return settings.get("list", []), settings.get("labels", {})


def get_staff_statuses() -> list[str]:
    settings = get_settings("staff_statuses")
    return settings.get("list", ["active", "inactive", "deactivated"])


def get_salary_types() -> list[str]:
    return ["weekly"]


def get_settlement_cycles() -> list[str]:
    return ["weekly"]


def get_app_config() -> dict:
    return get_settings("app_config")


def get_working_config() -> dict:
    config = get_settings("app_config")
    return {
        "standard_hours_per_day": config.get("standard_hours_per_day", 8),
        "overtime_grace_minutes": config.get("overtime_grace_minutes", 30),
        "working_days_per_week": config.get("working_days_per_week", 6),
    }
