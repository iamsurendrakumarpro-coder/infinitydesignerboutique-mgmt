"""
middleware/response.py - Standardised JSON response envelope for enterprise APIs.

Every API response follows this structure::

    {
        "success":    bool,
        "data":       dict | list | null,
        "error":      { "code": str, "message": str, "details": ... } | null,
        "meta":       { "request_id": str, "timestamp": str, "version": str } | null,
        "pagination": { "page": int, "per_page": int, "total": int, "pages": int } | null,
    }
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import jsonify, request, g

API_VERSION = "1.0.0"


# -- Error codes ---------------------------------------------------------------

class ErrorCode:
    """Standardised error codes for API responses."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    FIRST_LOGIN_REQUIRED = "FIRST_LOGIN_REQUIRED"


# -- Request ID ----------------------------------------------------------------

def get_request_id() -> str:
    """Return a unique request ID (generated per-request, cached in flask.g)."""
    if not hasattr(g, "request_id"):
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return g.request_id


# -- Response builders ---------------------------------------------------------

def _build_meta() -> dict:
    return {
        "request_id": get_request_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
    }


def api_success(
    data: Any = None,
    message: str | None = None,
    status_code: int = 200,
    pagination: dict | None = None,
) -> tuple:
    """Build a successful JSON response."""
    body: dict[str, Any] = {
        "success": True,
        "data": data,
        "error": None,
        "meta": _build_meta(),
    }
    if message:
        body["message"] = message
    if pagination:
        body["pagination"] = pagination
    return jsonify(body), status_code


def api_error(
    message: str,
    code: str = ErrorCode.BAD_REQUEST,
    status_code: int = 400,
    details: Any = None,
) -> tuple:
    """Build an error JSON response."""
    body: dict[str, Any] = {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
        "meta": _build_meta(),
    }
    if details:
        body["error"]["details"] = details
    return jsonify(body), status_code


def api_created(data: Any = None, message: str = "Resource created.") -> tuple:
    return api_success(data=data, message=message, status_code=201)


def api_not_found(message: str = "Resource not found.") -> tuple:
    return api_error(message, ErrorCode.NOT_FOUND, 404)


def api_unauthorized(message: str = "Authentication required.") -> tuple:
    return api_error(message, ErrorCode.AUTHENTICATION_REQUIRED, 401)


def api_forbidden(message: str = "Access denied.") -> tuple:
    return api_error(message, ErrorCode.PERMISSION_DENIED, 403)


def api_conflict(message: str = "Resource conflict.") -> tuple:
    return api_error(message, ErrorCode.CONFLICT, 409)


def api_validation_error(errors: dict) -> tuple:
    """Return 422 with field-level validation errors."""
    return api_error(
        "Validation failed.",
        ErrorCode.VALIDATION_ERROR,
        422,
        details=errors,
    )


# -- Pagination helper ---------------------------------------------------------

def paginate_params() -> tuple[int, int]:
    """Extract page and per_page from query string with safe defaults."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20
    return page, per_page


def paginate_list(items: list, page: int, per_page: int) -> tuple[list, dict]:
    """Paginate an in-memory list and return (page_items, pagination_meta)."""
    total = len(items)
    pages = math.ceil(total / per_page) if total > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }
