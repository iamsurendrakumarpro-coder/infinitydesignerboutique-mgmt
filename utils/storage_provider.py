"""
utils/storage_provider.py - Storage abstraction for Firebase and AWS S3.

This module allows gradual migration by selecting the storage backend via env:

    APP_STORAGE_PROVIDER=firebase|s3

Default is firebase for backward compatibility.
"""
from __future__ import annotations

import os
import importlib
from functools import lru_cache

from utils.firebase_client import get_storage_bucket, generate_signed_url
from utils.logger import get_logger

log = get_logger(__name__)


def _load_boto3():
    try:
        return importlib.import_module("boto3")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("boto3 is not installed. Install boto3 to use APP_STORAGE_PROVIDER=s3") from exc


def get_storage_provider() -> str:
    provider = str(os.getenv("APP_STORAGE_PROVIDER", "firebase")).strip().lower()
    if provider not in ("firebase", "s3"):
        return "firebase"
    return provider


@lru_cache(maxsize=1)
def _get_s3_client():
    boto3 = _load_boto3()
    region = str(os.getenv("AWS_REGION", "")).strip() or None
    return boto3.client("s3", region_name=region)


@lru_cache(maxsize=1)
def _get_s3_bucket() -> str:
    bucket = str(os.getenv("AWS_S3_BUCKET", "")).strip()
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET is required when APP_STORAGE_PROVIDER=s3")
    return bucket


def upload_bytes(
    storage_path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
    make_public: bool = False,
) -> tuple[bool, str, dict]:
    """
    Upload raw bytes to the configured storage provider.

    Returns (success, error_message, metadata).
    metadata currently includes: storage_path, public_url(optional).
    """
    provider = get_storage_provider()

    try:
        if provider == "s3":
            client = _get_s3_client()
            bucket = _get_s3_bucket()
            params = {
                "Bucket": bucket,
                "Key": storage_path,
                "Body": file_bytes,
                "ContentType": content_type,
            }
            if make_public:
                params["ACL"] = "public-read"
            client.put_object(**params)

            public_url = None
            if make_public:
                region = str(os.getenv("AWS_REGION", "")).strip() or "us-east-1"
                if region == "us-east-1":
                    public_url = f"https://{bucket}.s3.amazonaws.com/{storage_path}"
                else:
                    public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{storage_path}"

            return True, "", {"storage_path": storage_path, "public_url": public_url}

        bucket = get_storage_bucket()
        blob = bucket.blob(storage_path)
        blob.upload_from_string(file_bytes, content_type=content_type)
        public_url = None
        if make_public:
            blob.make_public()
            public_url = blob.public_url
        return True, "", {"storage_path": storage_path, "public_url": public_url}
    except Exception as exc:  # noqa: BLE001
        log.error("Storage upload failed | provider=%s | path=%s | error=%s", provider, storage_path, exc)
        return False, str(exc), {}


def delete_object(storage_path: str) -> tuple[bool, str]:
    """Delete an object from the configured storage provider."""
    provider = get_storage_provider()
    try:
        if provider == "s3":
            client = _get_s3_client()
            client.delete_object(Bucket=_get_s3_bucket(), Key=storage_path)
            return True, ""

        bucket = get_storage_bucket()
        bucket.blob(storage_path).delete()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        log.warning("Storage delete failed | provider=%s | path=%s | error=%s", provider, storage_path, exc)
        return False, str(exc)


def generate_download_url(storage_path: str, expiration_minutes: int = 60) -> str:
    """Generate a time-limited download URL from the configured provider."""
    provider = get_storage_provider()

    if provider == "s3":
        client = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _get_s3_bucket(), "Key": storage_path},
            ExpiresIn=max(60, int(expiration_minutes * 60)),
        )

    return generate_signed_url(storage_path, expiration_minutes=expiration_minutes)
