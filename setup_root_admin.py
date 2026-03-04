"""
setup_root_admin.py – One-time script to seed the Root Admin account.

Run once after initial Firebase project setup:

    python setup_root_admin.py

Environment variables (from .env):
    ROOT_ADMIN_FULL_NAME  – Display name for the root admin
    ROOT_ADMIN_PHONE      – 10-digit phone number (login ID)
    ROOT_ADMIN_PIN        – Initial 4-digit PIN (must be changed on first login)
    FIREBASE_*            – Firebase credentials

The root admin has is_root=True and is never shown in the admin user list.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Logging must be initialised before any boutique module imports ─────────────
from config import get_config
cfg = get_config()

from utils.logger import init_logging, get_logger
init_logging(log_dir=cfg.LOG_DIR, log_level=cfg.LOG_LEVEL)
log = get_logger(__name__)


def run() -> None:
    full_name = os.getenv("ROOT_ADMIN_FULL_NAME", "Owner")
    phone = os.getenv("ROOT_ADMIN_PHONE", "")
    pin = os.getenv("ROOT_ADMIN_PIN", "0000")

    if not phone:
        log.error("ROOT_ADMIN_PHONE is not set in .env. Aborting.")
        sys.exit(1)

    if len(phone) != 10 or not phone.isdigit():
        log.error("ROOT_ADMIN_PHONE must be exactly 10 digits. Got: %s", phone)
        sys.exit(1)

    if len(pin) != 4 or not pin.isdigit():
        log.error("ROOT_ADMIN_PIN must be exactly 4 digits. Got: %s", pin)
        sys.exit(1)

    from utils.firebase_client import get_firestore
    db = get_firestore()

    # Check if root already exists
    existing = list(
        db.collection("admins")
        .where("is_root", "==", True)
        .limit(1)
        .stream()
    )
    if existing:
        log.warning(
            "Root admin already exists (user_id=%s). Skipping creation.",
            existing[0].id,
        )
        print(f"\n[SKIP] Root admin already exists: {existing[0].to_dict().get('full_name')} / phone={existing[0].to_dict().get('phone_number')}")
        return

    # Check phone uniqueness
    from services.user_service import is_phone_taken
    if is_phone_taken(phone):
        log.error("Phone %s is already registered. Cannot create root admin.", phone)
        sys.exit(1)

    from services.user_service import create_admin
    success, error, doc = create_admin(
        {"full_name": full_name, "phone_number": phone, "temp_pin": pin, "is_root": True},
        created_by="system",
    )

    if not success:
        log.error("Failed to create root admin: %s", error)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ROOT ADMIN CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Full Name    : {full_name}")
    print(f"  Phone Number : {phone}")
    print(f"  Initial PIN  : {pin}  ← CHANGE THIS ON FIRST LOGIN")
    print(f"  User ID      : {doc.get('user_id')}")
    print("=" * 60)
    print("\n[IMPORTANT] Login and change your PIN immediately!\n")

    log.info(
        "Root admin seeded | user_id=%s | phone=%s",
        doc.get("user_id"), phone,
    )


if __name__ == "__main__":
    run()
