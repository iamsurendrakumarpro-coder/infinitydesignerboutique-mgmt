"""
modules/auth/routes.py – Authentication Blueprint.

Page Routes
-----------
GET  /               → Login page
GET  /change-pin     → PIN change page (first-login enforcement)

API Routes
----------
POST /api/auth/login      – Phone + PIN login
POST /api/auth/logout     – Logout
POST /api/auth/change-pin – Change PIN
GET  /api/auth/me         – Current session info
"""
from __future__ import annotations

from flask import (
    Blueprint,
    request,
    session,
    jsonify,
    redirect,
    url_for,
    render_template,
    current_app,
)

from services.auth_service import authenticate_user, change_pin
from utils.validators import validate_phone, validate_pin
from utils.logger import get_logger

log = get_logger(__name__)

auth_bp = Blueprint("auth", __name__)


# ── Page routes ───────────────────────────────────────────────────────────────

@auth_bp.get("/")
def login_page():
    """Render the login page.  Redirect if already logged in."""
    if "user_id" in session:
        return _redirect_by_role()
    return render_template("index.html", boutique_name=current_app.config["BOUTIQUE_NAME"])


@auth_bp.get("/change-pin")
def change_pin_page():
    """Render the PIN-change page."""
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    return render_template(
        "change_pin.html",
        boutique_name=current_app.config["BOUTIQUE_NAME"],
        user=_session_user(),
    )


# ── API routes ────────────────────────────────────────────────────────────────

@auth_bp.post("/api/auth/login")
def api_login():
    """Authenticate a user with phone + PIN."""
    body = request.get_json(silent=True) or {}
    phone = str(body.get("phone_number", "")).strip()
    pin = str(body.get("pin", "")).strip()

    ok, err = validate_phone(phone)
    if not ok:
        return jsonify({"success": False, "error": err}), 400

    ok, err = validate_pin(pin)
    if not ok:
        return jsonify({"success": False, "error": err}), 400

    log.info("Login API call | phone=%s | ip=%s", phone, request.remote_addr)
    result = authenticate_user(phone, pin)

    if result is None:
        return jsonify({"success": False, "error": "Invalid phone number or PIN."}), 401

    if result.get("blocked"):
        return jsonify({"success": False, "error": result.get("reason", "Access denied.")}), 403

    # Populate session
    session.clear()
    session["user_id"] = result["user_id"]
    session["role"] = result["role"]
    session["full_name"] = result["full_name"]
    session["phone_number"] = result["phone_number"]
    session["is_first_login"] = result.get("is_first_login", False)
    session.permanent = True

    redirect_url = url_for("auth.change_pin_page") if result.get("is_first_login") else _redirect_url_for_role(result["role"])

    log.info(
        "Login successful | user_id=%s | role=%s | first_login=%s",
        result["user_id"], result["role"], result.get("is_first_login"),
    )
    return jsonify({
        "success": True,
        "role": result["role"],
        "full_name": result["full_name"],
        "is_first_login": result.get("is_first_login", False),
        "redirect_url": redirect_url,
    })


@auth_bp.post("/api/auth/logout")
def api_logout():
    """Clear session and log out."""
    user_id = session.get("user_id", "unknown")
    role = session.get("role", "unknown")
    session.clear()
    log.info("Logout | user_id=%s | role=%s", user_id, role)
    return jsonify({"success": True, "redirect_url": url_for("auth.login_page")})


@auth_bp.post("/api/auth/change-pin")
def api_change_pin():
    """Change the authenticated user's PIN."""
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    body = request.get_json(silent=True) or {}
    new_pin = str(body.get("new_pin", "")).strip()
    old_pin = str(body.get("old_pin", "")).strip() or None

    ok, err = validate_pin(new_pin)
    if not ok:
        return jsonify({"success": False, "error": err}), 400

    is_first = session.get("is_first_login", False)
    user_id = session["user_id"]
    role = session["role"]

    success, error = change_pin(user_id, role, old_pin, new_pin, is_first_login=is_first)
    if not success:
        return jsonify({"success": False, "error": error}), 400

    session["is_first_login"] = False
    redirect_url = _redirect_url_for_role(role)

    log.info("PIN change API success | user_id=%s | role=%s", user_id, role)
    return jsonify({"success": True, "redirect_url": redirect_url})


@auth_bp.get("/api/auth/me")
def api_me():
    """Return current session info."""
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
    return jsonify({"success": True, "user": _session_user()})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_user() -> dict:
    return {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "full_name": session.get("full_name"),
        "phone_number": session.get("phone_number"),
        "is_first_login": session.get("is_first_login", False),
    }


def _redirect_url_for_role(role: str) -> str:
    if role == "admin":
        return url_for("admin.dashboard")
    return url_for("staff_views.duty_station")


def _redirect_by_role():
    role = session.get("role", "")
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("staff_views.duty_station"))
