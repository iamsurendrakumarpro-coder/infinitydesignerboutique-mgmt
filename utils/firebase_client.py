"""
utils/firebase_client.py - Firebase Admin SDK initialisation.

Usage::

    from utils.firebase_client import get_firestore, get_storage_bucket, generate_signed_url

The module is lazily initialised on first use via _init_firebase().
All Firebase interactions in the app go through these helpers so
that credentials are managed in a single place.

Environment variables consumed:
    FIREBASE_CREDENTIALS_PATH  - Path to the service-account JSON file.
    FIREBASE_PROJECT_ID        - GCP project ID (optional if credentials embed it).
    FIREBASE_STORAGE_BUCKET    - Default Storage bucket name (e.g. my-project.appspot.com).
"""
from __future__ import annotations

import os
from datetime import timedelta
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore, storage as fb_storage
from google.cloud import storage as gcs_storage  # noqa: F401 - used by generate_signed_url
from google.cloud.firestore_v1 import Client as FirestoreClient

from utils.logger import get_logger

log = get_logger(__name__)

# Module-level singleton - populated by _init_firebase() on first use.
_app: firebase_admin.App | None = None


def _resolve_storage_bucket(configured_bucket: str, project_id: str) -> str:
    """
    Resolve a safe Firebase Storage bucket name from environment config.

    If the configured bucket is missing or clearly invalid (e.g. contains
    underscores), fall back to the project's default appspot bucket.
    """
    bucket = (configured_bucket or "").strip()
    project = (project_id or "").strip()

    if not bucket and project:
        return f"{project}.appspot.com"

    # GCS bucket names cannot contain underscores.
    if "_" in bucket and project:
        return f"{project}.appspot.com"

    return bucket


def _init_firebase() -> firebase_admin.App:
    """
    Initialise the Firebase Admin SDK exactly once (idempotent).

    Reads credentials from the path set in FIREBASE_CREDENTIALS_PATH.
    Falls back to Application Default Credentials if the file is absent
    (useful in Cloud Run / GCE environments).

    Returns the initialised App object.
    """
    global _app
    if _app is not None:
        # Already initialised - return the existing App to avoid double-init errors.
        log.debug("Firebase already initialised - reusing existing App.")
        return _app

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    configured_bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    storage_bucket = _resolve_storage_bucket(configured_bucket, project_id)

    log.info(
        "Initialising Firebase Admin SDK | credentials=%s | project=%s | bucket=%s",
        cred_path,
        project_id,
        storage_bucket,
    )

    if configured_bucket and configured_bucket != storage_bucket:
        log.warning(
            "Invalid FIREBASE_STORAGE_BUCKET '%s'; falling back to '%s'.",
            configured_bucket,
            storage_bucket,
        )

    if os.path.exists(cred_path):
        # Explicit service-account credentials file (local dev and CI).
        cred = credentials.Certificate(cred_path)
        log.info("Loaded service-account credentials from: %s", cred_path)
    else:
        # Fall back to Application Default Credentials (Cloud Run, GCE, etc.).
        cred = credentials.ApplicationDefault()
        log.warning(
            "Credentials file not found at '%s'. "
            "Falling back to Application Default Credentials.",
            cred_path,
        )

    # Build the options dict; only include non-empty values to avoid SDK errors.
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
    """
    Return a singleton Firestore client.

    Thread-safe because lru_cache holds a single cached instance.
    Initialises Firebase if it has not been initialised yet.
    """
    _init_firebase()
    db = firestore.client()
    log.debug("Firestore client obtained.")
    return db


def get_storage_bucket():
    """
    Return the default Firebase Storage bucket handle.

    Initialises Firebase if it has not been initialised yet.
    The bucket name is read from the FIREBASE_STORAGE_BUCKET env var.
    """
    _init_firebase()
    bucket = fb_storage.bucket()
    log.debug("Firebase Storage bucket obtained: %s", bucket.name)
    return bucket


def generate_signed_url(blob_name: str, expiration_minutes: int = 60) -> str:
    """
    Generate a V4 signed GET URL for a GCS object.

    Parameters
    ----------
    blob_name          : Path to the object inside the Storage bucket (e.g. 'gallery/uid/img.jpg').
    expiration_minutes : How long the signed URL remains valid. Defaults to 60 minutes.

    Returns a fully-qualified HTTPS signed URL string.
    """
    bucket = get_storage_bucket()
    blob = bucket.blob(blob_name)
    url = blob.generate_signed_url(
        expiration=timedelta(minutes=expiration_minutes),
        version="v4",
        method="GET",
    )
    return url
