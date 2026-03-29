"""
middleware/rate_limit.py - Request rate limiting for enterprise API protection.

Uses Flask-Limiter with in-memory storage (suitable for single-instance).
For multi-instance deployments, swap to Redis storage.
"""
from __future__ import annotations

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from utils.logger import get_logger

log = get_logger(__name__)

# Module-level limiter instance (configured in init_rate_limiting)
limiter: Limiter | None = None


def init_rate_limiting(app: Flask) -> Limiter:
    """Initialise and attach Flask-Limiter to the application."""
    global limiter

    default_limit = app.config.get("RATE_LIMIT_DEFAULT", "200 per minute")
    auth_limit = app.config.get("RATE_LIMIT_AUTH", "10 per minute")

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[default_limit],
        storage_uri="memory://",
    )

    # Stricter limits on auth endpoints
    limiter.limit(auth_limit)(app.view_functions.get("auth.api_login", lambda: None))

    log.info(
        "Rate limiting enabled | default=%s | auth=%s",
        default_limit,
        auth_limit,
    )
    return limiter


def get_limiter() -> Limiter | None:
    return limiter
