"""
utils/firebase_client.py – Firebase Admin SDK initialisation.

Usage::

    from utils.firebase_client import get_firestore, get_storage_bucket

The module is lazily initialised on first use.
All Firebase interactions in the app go through these helpers so
that credentials are managed in one place.
"""
from __future__ import annotations

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1 import Client as FirestoreClient
from firebase_admin import storage as fb_storage

from utils.logger import get_logger

log = get_logger(__name__)

_app: firebase_admin.App | None = None


def _init_firebase() -> firebase_admin.App:
    """
    Initialise the Firebase Admin SDK exactly once.
    Reads credentials from the path set in FIREBASE_CREDENTIALS_PATH.
    Returns the initialised App object.
    """
    global _app
    if _app is not None:
        log.debug("Firebase already initialised – reusing existing App.")
        return _app

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    log.info(
        "Initialising Firebase Admin SDK | credentials=%s | project=%s | bucket=%s",
        cred_path,
        project_id,
        storage_bucket,
    )

    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        log.info("Loaded service-account credentials from: %s", cred_path)
    else:
        # Fall back to Application Default Credentials (e.g. Cloud Run / GCE)
        cred = credentials.ApplicationDefault()
        log.warning(
            "Credentials file not found at '%s'. "
            "Falling back to Application Default Credentials.",
            cred_path,
        )

    options: dict = {}
    if project_id:
        options["projectId"] = project_id
    if storage_bucket:
        options["storageBucket"] = storage_bucket

    _app = firebase_admin.initialize_app(cred, options)
    log.info("Firebase Admin SDK initialised successfully. App name: %s", _app.name)
    return _app


@lru_cache(maxsize=1)
def get_firestore() -> FirestoreClient:
    """Return a singleton Firestore client (thread-safe via lru_cache)."""
    _init_firebase()
    db = firestore.client()
    log.debug("Firestore client obtained.")
    return db


def get_storage_bucket():
    """Return the default Firebase Storage bucket handle."""
    _init_firebase()
    bucket = fb_storage.bucket()
    log.debug("Firebase Storage bucket obtained: %s", bucket.name)
    return bucket
