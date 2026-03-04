"""
config.py – Central configuration for Infinity Designer Boutique Management.

All environment-dependent values live here so that changing a single .env file
is all that is needed to switch between development and production.
"""
import os
import logging
from datetime import timedelta
from dotenv import load_dotenv

# ── Load .env (silently ignored if file does not exist) ──────────────────────
load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    # ── Flask Core ────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    TESTING: bool = False

    # ── Session ───────────────────────────────────────────────────────────────
    SESSION_TYPE: str = "filesystem"
    SESSION_PERMANENT: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(
        seconds=int(os.getenv("SESSION_LIFETIME_SECONDS", "28800"))
    )
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── Firebase ─────────────────────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json"
    )
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # ── Application ──────────────────────────────────────────────────────────
    BOUTIQUE_NAME: str = os.getenv("BOUTIQUE_NAME", "Infinity Designer Boutique")

    # ── Timezone ─────────────────────────────────────────────────────────────
    TIMEZONE: str = "Asia/Kolkata"

    # ── PIN Policy ────────────────────────────────────────────────────────────
    PIN_LENGTH: int = 4

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR: str = os.path.join(os.path.dirname(__file__), "logs")
    LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # ── Staff Defaults ────────────────────────────────────────────────────────
    DEFAULT_LOGIN_TIME: str = "10:00"    # 24-hr  (10 AM IST)
    DEFAULT_LOGOUT_TIME: str = "19:00"   # 24-hr  ( 7 PM IST)

    # ── Allowed Designations ──────────────────────────────────────────────────
    DESIGNATIONS: list[str] = ["cutting_master", "handwork_expert", "tailor"]
    DESIGNATION_LABELS: dict[str, str] = {
        "cutting_master": "Cutting Master",
        "handwork_expert": "Handwork Expert",
        "tailor": "Tailor",
    }

    # ── Staff Status Values ───────────────────────────────────────────────────
    STAFF_STATUSES: list[str] = ["active", "inactive", "deactivated"]


class DevelopmentConfig(Config):
    DEBUG: bool = True


class ProductionConfig(Config):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True   # HTTPS only in production


# ── Config selector ──────────────────────────────────────────────────────────
_env_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config() -> Config:
    """Return the config object matching the current FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development").lower()
    return _env_map.get(env, DevelopmentConfig)()
