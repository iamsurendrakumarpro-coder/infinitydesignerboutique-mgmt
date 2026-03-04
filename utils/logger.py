"""
utils/logger.py – Centralised, structured logging for the boutique app.

Features
--------
* Rotating file handler  (logs/app.log – up to 10 MB × 5 backups)
* Console handler for development
* ISO-8601 timestamps locked to IST
* Caller information injected automatically (module, line)
* Convenience helpers: get_logger(), audit_log()
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from datetime import datetime

import pytz

# ── Constants ─────────────────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
LOG_FORMAT = (
    "%(asctime)s [%(levelname)-8s] [%(name)s:%(lineno)d] %(message)s"
)
AUDIT_FORMAT = (
    "%(asctime)s [AUDIT] [%(name)s] %(message)s"
)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_initialised: bool = False
_root_logger: logging.Logger | None = None


class ISTFormatter(logging.Formatter):
    """Custom formatter that stamps logs with IST (Asia/Kolkata) timezone."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        utc_dt = datetime.utcfromtimestamp(record.created).replace(tzinfo=pytz.utc)
        ist_dt = utc_dt.astimezone(IST)
        return ist_dt.strftime(datefmt or DATE_FORMAT)


def init_logging(log_dir: str, log_level: str = "DEBUG", max_bytes: int = 10_485_760, backup_count: int = 5) -> None:
    """
    Bootstrap the application-wide logging infrastructure.

    Should be called **once** at application startup (app.py).
    Subsequent calls are ignored.

    Parameters
    ----------
    log_dir       : Directory where rotating log files are written.
    log_level     : Minimum log level (e.g. 'DEBUG', 'INFO').
    max_bytes     : Maximum bytes per log file before rotation.
    backup_count  : Number of rotated backup files to keep.
    """
    global _initialised, _root_logger
    if _initialised:
        return

    os.makedirs(log_dir, exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.DEBUG)

    # ── Root logger ──────────────────────────────────────────────────────────
    root = logging.getLogger("boutique")
    root.setLevel(numeric_level)
    root.propagate = False

    formatter = ISTFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── File handler (rotating) ──────────────────────────────────────────────
    log_path = os.path.join(log_dir, "app.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # ── Audit-specific file handler ──────────────────────────────────────────
    audit_path = os.path.join(log_dir, "audit.log")
    audit_handler = logging.handlers.RotatingFileHandler(
        audit_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(ISTFormatter(fmt=AUDIT_FORMAT, datefmt=DATE_FORMAT))
    audit_logger = logging.getLogger("boutique.audit")
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = True

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _root_logger = root
    _initialised = True

    root.info(
        "Logging initialised | level=%s | log_dir=%s | log_file=%s",
        log_level,
        log_dir,
        log_path,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'boutique' namespace.

    Usage::

        log = get_logger(__name__)
        log.info("Something happened")

    Parameters
    ----------
    name : Typically ``__name__`` of the calling module.
    """
    return logging.getLogger(f"boutique.{name}")


def audit_log(actor_id: str, action: str, target: str, detail: str = "") -> None:
    """
    Write a structured audit event to logs/audit.log.

    Parameters
    ----------
    actor_id : user_id of the person performing the action.
    action   : Short verb phrase, e.g. "LOGIN", "CREATE_STAFF", "PUNCH_IN".
    target   : Resource affected, e.g. "staff/abc123".
    detail   : Optional extra context.
    """
    log = logging.getLogger("boutique.audit")
    log.info(
        "actor=%s | action=%s | target=%s | detail=%s",
        actor_id,
        action,
        target,
        detail,
    )


# ── Structured logging helpers ────────────────────────────────────────────────

def log_request(logger: logging.Logger, method: str, path: str, user_id: str | None = None, **extra: object) -> None:
    """Log an incoming API request with structured context."""
    parts = [f"REQUEST {method} {path}"]
    if user_id:
        parts.append(f"user_id={user_id}")
    for k, v in extra.items():
        parts.append(f"{k}={v}")
    logger.info(" | ".join(parts))


def log_response(logger: logging.Logger, method: str, path: str, status: int, **extra: object) -> None:
    """Log an outgoing API response with structured context."""
    parts = [f"RESPONSE {method} {path}", f"status={status}"]
    for k, v in extra.items():
        parts.append(f"{k}={v}")
    logger.info(" | ".join(parts))


def log_service_call(logger: logging.Logger, service: str, operation: str, **extra: object) -> None:
    """Log a service-layer operation."""
    parts = [f"SERVICE {service}.{operation}"]
    for k, v in extra.items():
        parts.append(f"{k}={v}")
    logger.info(" | ".join(parts))


def log_error(logger: logging.Logger, operation: str, error: str | Exception, **extra: object) -> None:
    """Log an error with structured context."""
    parts = [f"ERROR in {operation}", f"error={error}"]
    for k, v in extra.items():
        parts.append(f"{k}={v}")
    logger.error(" | ".join(parts))
