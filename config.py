"""
config.py - Central configuration for Infinity Designer Boutique Management.

All environment-dependent values live here so that changing a single .env file
is all that is needed to switch between development and production.

Usage::

    from config import get_config
    cfg = get_config()

Environment
-----------
Set FLASK_ENV=production (or development) to select the appropriate config class.
All sensitive values MUST be supplied via environment variables or a .env file;
never hard-code credentials in this file.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# -- Load .env (silently ignored if file does not exist) ----------------------
load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    # -- Flask Core ------------------------------------------------------------
    # FLASK_SECRET_KEY must be a long random value in production.
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    TESTING: bool = False

    # -- Session ---------------------------------------------------------------
    # Sessions are stored server-side in the filesystem; the cookie only holds
    # an opaque session ID, making it safe to set HTTPONLY + SAMESITE.
    SESSION_TYPE: str = "filesystem"
    SESSION_PERMANENT: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(
        seconds=int(os.getenv("SESSION_LIFETIME_SECONDS", "28800"))  # Default: 8 hours
    )
    SESSION_COOKIE_HTTPONLY: bool = True   # Prevent JS access to the session cookie
    SESSION_COOKIE_SAMESITE: str = "Lax"  # CSRF protection for same-site requests

    # -- Firebase -------------------------------------------------------------
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json"
    )
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # -- Application ----------------------------------------------------------
    BOUTIQUE_NAME: str = os.getenv("BOUTIQUE_NAME", "Infinity Designer Boutique")

    # -- Timezone -------------------------------------------------------------
    # All timestamps stored in and displayed as IST (UTC+5:30).
    TIMEZONE: str = "Asia/Kolkata"

    # -- PIN Policy ------------------------------------------------------------
    PIN_LENGTH: int = 4  # 4-digit numeric PIN for all users

    # -- Logging ---------------------------------------------------------------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR: str = os.path.join(os.path.dirname(__file__), "logs")
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB per log file before rotation
    LOG_BACKUP_COUNT: int = 5              # Keep last 5 rotated log files

    # -- Staff Defaults --------------------------------------------------------
    DEFAULT_LOGIN_TIME: str = "10:00"   # 24-hr format (10 AM IST)
    DEFAULT_LOGOUT_TIME: str = "19:00"  # 24-hr format ( 7 PM IST)

    # -- Allowed Designations --------------------------------------------------
    # Used by validators to reject unknown designation values.
    DESIGNATIONS: list[str] = [
        "cutting_master",
        "tailor",
        "embroidery_artist",
        "handwork_expert",
        "designer",
        "helper",
    ]
    DESIGNATION_LABELS: dict[str, str] = {
        "cutting_master":    "Cutting Master",
        "tailor":            "Tailor",
        "embroidery_artist": "Embroidery Artist",
        "handwork_expert":   "Handwork Expert",
        "designer":          "Designer",
        "helper":            "Helper",
    }

    # -- Staff Status Values ---------------------------------------------------
    # "active"      - Can punch in/out and submit requests.
    # "inactive"    - Temporarily disabled (e.g. on leave).
    # "deactivated" - Permanently removed from active roster.
    STAFF_STATUSES: list[str] = ["active", "inactive", "deactivated"]

    # -- Overtime & Settlement -------------------------------------------------
    # Overtime is only triggered when an employee works more than
    # (STANDARD_HOURS_PER_DAY * 60 + OVERTIME_GRACE_MINUTES) minutes in a day.
    OVERTIME_GRACE_MINUTES: int = 60
    WORKING_DAYS_PER_WEEK: int = 6    # Monday - Saturday
    STANDARD_HOURS_PER_DAY: int = 8

    # -- Salary & Settlement Cycle ---------------------------------------------
    # salary_type governs which salary field is stored on the staff document.
    # settlement_cycle is admin-configurable per staff member.
    SALARY_TYPES: list[str] = ["weekly", "monthly"]
    SETTLEMENT_CYCLES: list[str] = ["weekly", "monthly"]
    MONTHLY_WORKING_DAYS: int = 26   # Standard working days per month (Mon-Sat)

    # -- CORS ------------------------------------------------------------------
    # Comma-separated list of allowed origins from CORS_ORIGINS env var.
    # Development default permits Vite (5173) and Create-React-App (3000) dev servers.
    CORS_ORIGINS: list[str] = [
        s.strip()
        for s in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
        if s.strip()
    ]


class DevelopmentConfig(Config):
    """Development overrides: verbose logging, debug mode on."""
    DEBUG: bool = True


class ProductionConfig(Config):
    """Production overrides: debug off, HTTPS-only cookies, empty CORS default."""
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True  # Only send cookie over HTTPS
    CORS_ORIGINS: list[str] = [
        s.strip()
        for s in os.getenv("CORS_ORIGINS", "").split(",")
        if s.strip()
    ]


# -- Config selector ----------------------------------------------------------
_env_map: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
}


def get_config() -> Config:
    """
    Return the config object matching the current FLASK_ENV.
    Defaults to DevelopmentConfig if FLASK_ENV is unset or unknown.
    """
    env = os.getenv("FLASK_ENV", "development").lower()
    return _env_map.get(env, DevelopmentConfig)()
