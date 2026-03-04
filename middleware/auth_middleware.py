"""
middleware/auth_middleware.py – Authentication & RBAC decorators (JSON-only).

Decorators
----------
login_required(f)       – Any logged-in user.
admin_required(f)       – Admin role only.
staff_required(f)       – Staff role only.
first_login_check(f)    – Forces PIN change when is_first_login is True.

Session shape (stored server-side)
------------------------------------
session["user_id"]       : str
session["role"]          : "admin" | "staff"
session["is_first_login"]: bool
session["full_name"]     : str
session["phone_number"]  : str
"""
from __future__ import annotations

from functools import wraps
from typing import Callable, Any

from flask import session, request, jsonify

from utils.logger import get_logger

log = get_logger(__name__)


def login_required(f: Callable) -> Callable:
    """Decorator: reject unauthenticated requests with JSON 401."""
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            log.warning(
                "Unauthenticated access attempt | path=%s | ip=%s",
                request.path,
                request.remote_addr,
            )
            return jsonify({"success": False, "error": "Authentication required."}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f: Callable) -> Callable:
    """Decorator: allow only admin-role users. Returns JSON 403."""
    @wraps(f)
    @login_required
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if session.get("role") != "admin":
            log.warning(
                "Forbidden admin access | user_id=%s | role=%s | path=%s",
                session.get("user_id"),
                session.get("role"),
                request.path,
            )
            return jsonify({"success": False, "error": "Admin access required."}), 403
        return f(*args, **kwargs)
    return decorated


def staff_required(f: Callable) -> Callable:
    """Decorator: allow only staff-role users. Returns JSON 403."""
    @wraps(f)
    @login_required
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if session.get("role") != "staff":
            log.warning(
                "Forbidden staff access | user_id=%s | role=%s | path=%s",
                session.get("user_id"),
                session.get("role"),
                request.path,
            )
            return jsonify({"success": False, "error": "Staff access required."}), 403
        return f(*args, **kwargs)
    return decorated


def first_login_check(f: Callable) -> Callable:
    """
    Decorator: if is_first_login is True, return JSON 403 requiring
    the user to change their PIN before accessing protected routes.
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if session.get("is_first_login"):
            log.info(
                "First-login PIN change enforced | user_id=%s",
                session.get("user_id"),
            )
            return jsonify({
                "success": False,
                "error": "You must change your PIN before continuing.",
                "first_login": True,
            }), 403
        return f(*args, **kwargs)
    return decorated
