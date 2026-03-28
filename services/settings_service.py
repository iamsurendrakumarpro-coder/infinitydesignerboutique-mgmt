"""
services/settings_service.py - Application settings management.

Firestore collection: settings/{config_type}

Provides dynamic configuration that was previously hardcoded in config.py.
Settings are cached in memory with a TTL to avoid frequent Firestore reads.

Config Types:
  - app_config: General settings (boutique name, timezone, shift times, etc.)
  - designations: Staff designation list and labels
  - staff_statuses: Allowed staff status values
  - salary_config: Salary types and settlement cycles
"""
from __future__ import annotations

import time
from typing import Any

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from utils.firebase_client import get_firestore
from utils.logger import get_logger, audit_log

log = get_logger(__name__)

_COLLECTION = "settings"
_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


# Default values (fallback if Firestore document doesn't exist)
_DEFAULTS = {
    "app_config": {
        "boutique_name": "Infinity Designer Boutique",
        "timezone": "Asia/Kolkata",
        "default_login_time": "10:00",
        "default_logout_time": "19:00",
        "standard_hours_per_day": 8,
        "overtime_grace_minutes": 60,
        "working_days_per_week": 6,
        "monthly_working_days": 26,
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
        "salary_types": ["weekly", "monthly"],
        "settlement_cycles": ["weekly", "monthly"],
    },
}


def get_settings(config_type: str, use_cache: bool = True) -> dict:
    """
    Get settings for a config type, with caching.

    Parameters
    ----------
    config_type : str
        One of: app_config, designations, staff_statuses, salary_config
    use_cache : bool
        Whether to use cached value if available (default True)

    Returns
    -------
    dict
        The settings dictionary for the config type
    """
    # Check cache first
    if use_cache and config_type in _CACHE:
        data, timestamp = _CACHE[config_type]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            log.debug("get_settings | config_type=%s | source=cache", config_type)
            return data

    # Fetch from Firestore
    try:
        db = get_firestore()
        doc = db.collection(_COLLECTION).document(config_type).get()
        if doc.exists:
            data = doc.to_dict()
            # Remove metadata fields from returned data
            data.pop("updated_at", None)
            data.pop("updated_by", None)
            log.debug("get_settings | config_type=%s | source=firestore", config_type)
        else:
            # Use defaults if document doesn't exist
            data = _DEFAULTS.get(config_type, {})
            log.info("get_settings | config_type=%s | source=defaults (doc not found)", config_type)
    except Exception as exc:
        log.error("get_settings failed | config_type=%s | error=%s", config_type, exc)
        data = _DEFAULTS.get(config_type, {})

    # Update cache
    _CACHE[config_type] = (data, time.time())
    return data


def update_settings(config_type: str, data: dict, updated_by: str) -> tuple[bool, str]:
    """
    Update settings for a config type.

    Parameters
    ----------
    config_type : str
        One of: app_config, designations, staff_statuses, salary_config
    data : dict
        The new settings data
    updated_by : str
        User ID of the admin making the change

    Returns
    -------
    tuple[bool, str]
        (success, error_message)
    """
    if config_type not in _DEFAULTS:
        return False, f"Invalid config type: {config_type}"

    try:
        db = get_firestore()
        ref = db.collection(_COLLECTION).document(config_type)

        # Merge with existing data to preserve fields not in the update
        existing_doc = ref.get()
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            existing_data.pop("updated_at", None)
            existing_data.pop("updated_by", None)
        else:
            existing_data = _DEFAULTS.get(config_type, {})

        # Merge: update existing with new data
        merged = {**existing_data, **data}
        merged["updated_at"] = SERVER_TIMESTAMP
        merged["updated_by"] = updated_by

        ref.set(merged)

        # Invalidate cache
        invalidate_cache(config_type)

        log.info("Settings updated | config_type=%s | by=%s | fields=%s",
                 config_type, updated_by, list(data.keys()))
        audit_log(updated_by, "UPDATE_SETTINGS", f"{_COLLECTION}/{config_type}")

        return True, ""

    except Exception as exc:
        log.error("update_settings failed | config_type=%s | error=%s", config_type, exc)
        return False, str(exc)


def invalidate_cache(config_type: str | None = None) -> None:
    """
    Invalidate cached settings.

    Parameters
    ----------
    config_type : str | None
        If provided, invalidate only that type. Otherwise invalidate all.
    """
    global _CACHE
    if config_type:
        _CACHE.pop(config_type, None)
        log.debug("Cache invalidated | config_type=%s", config_type)
    else:
        _CACHE = {}
        log.debug("Cache invalidated | all")


def get_all_settings() -> dict[str, dict]:
    """
    Get all settings for all config types.

    Returns
    -------
    dict[str, dict]
        Dictionary with config_type as key and settings as value
    """
    return {
        "app_config": get_settings("app_config"),
        "designations": get_settings("designations"),
        "staff_statuses": get_settings("staff_statuses"),
        "salary_config": get_settings("salary_config"),
    }


# -- Convenience functions for specific settings -------------------------------

def get_designations() -> tuple[list[str], dict[str, str]]:
    """
    Get designations list and labels.

    Returns
    -------
    tuple[list[str], dict[str, str]]
        (list of designation keys, dict of key -> label)
    """
    settings = get_settings("designations")
    return settings.get("list", []), settings.get("labels", {})


def get_staff_statuses() -> list[str]:
    """Get allowed staff status values."""
    settings = get_settings("staff_statuses")
    return settings.get("list", ["active", "inactive", "deactivated"])


def get_salary_types() -> list[str]:
    """Get allowed salary types."""
    settings = get_settings("salary_config")
    return settings.get("salary_types", ["weekly", "monthly"])


def get_settlement_cycles() -> list[str]:
    """Get allowed settlement cycles."""
    settings = get_settings("salary_config")
    return settings.get("settlement_cycles", ["weekly", "monthly"])


def get_app_config() -> dict:
    """Get app configuration settings."""
    return get_settings("app_config")


def get_working_config() -> dict:
    """
    Get working hours configuration.

    Returns
    -------
    dict
        Contains: standard_hours_per_day, overtime_grace_minutes,
                  working_days_per_week, monthly_working_days
    """
    config = get_settings("app_config")
    return {
        "standard_hours_per_day": config.get("standard_hours_per_day", 8),
        "overtime_grace_minutes": config.get("overtime_grace_minutes", 60),
        "working_days_per_week": config.get("working_days_per_week", 6),
        "monthly_working_days": config.get("monthly_working_days", 26),
    }
