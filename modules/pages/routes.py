"""
modules/pages/routes.py - Page-serving Blueprint.

Serves Jinja2 HTML templates for the PWA frontend.
All data fetching is done client-side via the /api/* JSON endpoints.
"""
from __future__ import annotations

from flask import Blueprint, render_template, session, redirect, url_for

from utils.logger import get_logger

log = get_logger(__name__)

pages_bp = Blueprint(
    "pages",
    __name__,
    template_folder="../../templates",
    static_folder="../../static",
    static_url_path="/static",
)


# -- Public pages --------------------------------------------------------------


@pages_bp.get("/")
def index():
    """Redirect to login or dashboard based on session."""
    if "user_id" in session:
        role = session.get("role")
        if not role:
            return redirect(url_for("pages.login"))
        if session.get("is_first_login"):
            return redirect(url_for("pages.change_pin"))
        if role in {"admin", "manager"}:
            return redirect(url_for("pages.admin_dashboard"))
        return redirect(url_for("pages.duty_station"))
    return redirect(url_for("pages.login"))


@pages_bp.get("/login")
def login():
    """Login page with number pad."""
    if "user_id" in session:
        return redirect(url_for("pages.index"))
    log.debug("Serving login page")
    return render_template("auth/login.html")


@pages_bp.get("/change-pin")
def change_pin():
    """Force PIN change page."""
    if "user_id" not in session:
        return redirect(url_for("pages.login"))
    user = _session_user()
    return render_template(
        "auth/change_pin.html",
        user=user,
        is_first_login=user.get("is_first_login", False),
    )


# -- Admin pages ---------------------------------------------------------------


@pages_bp.get("/admin/dashboard")
def admin_dashboard():
    """Admin dashboard overview."""
    if not _is_admin_or_manager():
        return redirect(url_for("pages.login"))
    return render_template("admin/dashboard.html", user=_session_user())


@pages_bp.get("/admin/staff")
def admin_staff_directory():
    """Staff directory listing."""
    if not _is_admin_or_manager():
        return redirect(url_for("pages.login"))
    return render_template("admin/staff_directory.html", user=_session_user())


@pages_bp.get("/admin/staff/create")
def admin_staff_create():
    """Staff creation form."""
    if not _is_admin():
        if _is_admin_or_manager():
            return redirect(url_for("pages.admin_staff_directory"))
        return redirect(url_for("pages.login"))
    return render_template(
        "admin/staff_form.html", user=_session_user(), mode="create"
    )


@pages_bp.get("/admin/staff/<staff_id>/edit")
def admin_staff_edit(staff_id: str):
    """Staff edit form."""
    if not _is_admin_or_manager():
        return redirect(url_for("pages.login"))
    return render_template(
        "admin/staff_form.html",
        user=_session_user(),
        mode="edit",
        staff_id=staff_id,
    )


@pages_bp.get("/admin/approvals")
def admin_approvals():
    """Pending approvals page."""
    if not _is_admin_or_manager():
        return redirect(url_for("pages.login"))
    return render_template("admin/approvals.html", user=_session_user())


@pages_bp.get("/admin/settlements")
def admin_settlements():
    """Settlement management page."""
    if _is_admin_or_manager() and not _is_admin():
        return redirect(url_for("pages.admin_dashboard"))
    if not _is_admin():
        return redirect(url_for("pages.login"))
    return render_template("admin/settlements.html", user=_session_user())


@pages_bp.get("/admin/settings")
def admin_settings():
    """Application settings page."""
    if _is_admin_or_manager() and not _is_admin():
        return redirect(url_for("pages.admin_dashboard"))
    if not _is_admin():
        return redirect(url_for("pages.login"))
    return render_template("admin/settings.html", user=_session_user())


@pages_bp.get("/admin/reimbursements")
def admin_reimbursements():
    """Legacy reimbursements route; redirects to unified settlements workspace."""
    if _is_admin_or_manager() and not _is_admin():
        return redirect(url_for("pages.admin_dashboard"))
    if not _is_admin():
        return redirect(url_for("pages.login"))
    return redirect("/admin/settlements?view=reimbursements")


# -- Staff pages ---------------------------------------------------------------


@pages_bp.get("/staff/duty")
def duty_station():
    """Duty station - daily task view."""
    if not _is_staff():
        if _is_admin_or_manager():
            return redirect(url_for("pages.admin_dashboard"))
        return redirect(url_for("pages.login"))
    if session.get("is_first_login"):
        return redirect(url_for("pages.change_pin"))
    return render_template("staff/duty_station.html", user=_session_user())


@pages_bp.get("/staff/money")
def my_money():
    """Staff earnings / money overview."""
    if not _is_staff():
        if _is_admin_or_manager():
            return redirect(url_for("pages.admin_dashboard"))
        return redirect(url_for("pages.login"))
    if session.get("is_first_login"):
        return redirect(url_for("pages.change_pin"))
    return render_template("staff/my_money.html", user=_session_user())


@pages_bp.get("/staff/leave")
def staff_leave():
    """Staff leave application and history page."""
    if not _is_staff():
        if _is_admin_or_manager():
            return redirect(url_for("pages.admin_dashboard"))
        return redirect(url_for("pages.login"))
    if session.get("is_first_login"):
        return redirect(url_for("pages.change_pin"))
    return render_template("staff/leave.html", user=_session_user())


@pages_bp.get("/staff/profile")
def staff_profile():
    """Staff profile page."""
    if not _is_staff():
        if _is_admin_or_manager():
            return redirect(url_for("pages.admin_dashboard"))
        return redirect(url_for("pages.login"))
    if session.get("is_first_login"):
        return redirect(url_for("pages.change_pin"))
    return render_template("staff/profile.html", user=_session_user())


# -- Helpers -------------------------------------------------------------------


def _session_user() -> dict[str, str | bool | None]:
    """Build a minimal user dict from the current Flask session."""
    return {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "full_name": session.get("full_name"),
        "phone_number": session.get("phone_number"),
        "is_first_login": session.get("is_first_login", False),
    }


def _is_admin() -> bool:
    """Return True when the session belongs to an admin user."""
    return "user_id" in session and session.get("role") == "admin"


def _is_admin_or_manager() -> bool:
    """Return True when the session belongs to an admin or manager user."""
    return "user_id" in session and session.get("role") in {"admin", "manager"}


def _is_staff() -> bool:
    """Return True when the session belongs to a staff-like user."""
    return "user_id" in session and session.get("role") == "staff"
