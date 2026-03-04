"""
middleware/auth_middleware.py – Authentication & RBAC decorators.

Decorators
----------
login_required(f)       – Any logged-in user.
admin_required(f)       – Admin role only.
staff_required(f)       – Staff role only.
first_login_required(f) – Forces PIN change when is_first_login is True.

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

from flask import session, redirect, url_for, request, jsonify

from utils.logger import get_logger

log = get_logger(__name__)


def _is_api_request() -> bool:
    """Return True if the request expects a JSON response."""
    return (
        request.path.startswith("/api/")
        or request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
    )


def login_required(f: Callable) -> Callable:
    """Decorator: reject unauthenticated requests."""
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            log.warning(
                "Unauthenticated access attempt | path=%s | ip=%s",
                request.path,
                request.remote_addr,
            )
            if _is_api_request():
                return jsonify({"success": False, "error": "Authentication required."}), 401
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f: Callable) -> Callable:
    """Decorator: allow only admin-role users."""
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
            if _is_api_request():
                return jsonify({"success": False, "error": "Admin access required."}), 403
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def staff_required(f: Callable) -> Callable:
    """Decorator: allow only staff-role users."""
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
            if _is_api_request():
                return jsonify({"success": False, "error": "Staff access required."}), 403
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def first_login_check(f: Callable) -> Callable:
    """
    Decorator applied to staff_required routes.
    If is_first_login is True, redirects staff to the PIN-change page
    before granting any access.
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if session.get("is_first_login"):
            log.info(
                "First-login PIN change enforced | user_id=%s",
                session.get("user_id"),
            )
            if _is_api_request():
                return jsonify({
                    "success": False,
                    "error": "You must change your PIN before continuing.",
                    "first_login": True,
                }), 403
            return redirect(url_for("auth.change_pin_page"))
        return f(*args, **kwargs)
    return decorated
