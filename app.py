"""
app.py – Infinity Designer Boutique Management System
Entry point for the Flask application.

Run (development):
    python app.py

Run (production via Gunicorn):
    gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
"""
from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, url_for
from flask_cors import CORS

from config import get_config, Config
from utils.logger import init_logging, get_logger

# ── Module imports ────────────────────────────────────────────────────────────
from modules.auth.routes import auth_bp
from modules.users.routes import users_bp, admin_bp
from modules.attendance.routes import attendance_bp, staff_views_bp


def create_app(config: Config | None = None) -> Flask:
    """
    Application factory.

    Parameters
    ----------
    config : Optional Config instance.  Defaults to environment-detected config.
    """
    cfg = config or get_config()

    # ── Logging first (before anything else) ─────────────────────────────────
    init_logging(
        log_dir=cfg.LOG_DIR,
        log_level=cfg.LOG_LEVEL,
        max_bytes=cfg.LOG_MAX_BYTES,
        backup_count=cfg.LOG_BACKUP_COUNT,
    )
    log = get_logger(__name__)
    log.info("=" * 70)
    log.info("Starting %s | env=%s | debug=%s", cfg.BOUTIQUE_NAME, os.getenv("FLASK_ENV", "development"), cfg.DEBUG)
    log.info("=" * 70)

    # ── Create Flask app ──────────────────────────────────────────────────────
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ── Apply config ──────────────────────────────────────────────────────────
    app.secret_key = cfg.SECRET_KEY
    app.config["DEBUG"] = cfg.DEBUG
    app.config["PERMANENT_SESSION_LIFETIME"] = cfg.PERMANENT_SESSION_LIFETIME
    app.config["SESSION_COOKIE_HTTPONLY"] = cfg.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = cfg.SESSION_COOKIE_SAMESITE
    app.config["BOUTIQUE_NAME"] = cfg.BOUTIQUE_NAME
    app.config["TIMEZONE"] = cfg.TIMEZONE
    app.config["DESIGNATIONS"] = cfg.DESIGNATIONS
    app.config["DESIGNATION_LABELS"] = cfg.DESIGNATION_LABELS

    # ── CORS (for development – restrict in production) ───────────────────────
    CORS(app, supports_credentials=True)

    # ── Initialise Firebase (eagerly so errors surface at startup) ────────────
    try:
        from utils.firebase_client import get_firestore
        get_firestore()
        log.info("Firebase / Firestore connected successfully.")
    except Exception as exc:  # noqa: BLE001
        log.error("Firebase initialisation failed: %s", exc)
        log.warning("App will start, but DB operations will fail until Firebase is configured.")

    # ── Register blueprints ───────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(staff_views_bp)

    log.info("Blueprints registered: auth, admin, users, attendance, staff_views")

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        log.warning("404 Not Found | path=%s", str(e))
        from flask import request, render_template
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found."}), 404
        return render_template("404.html", boutique_name=cfg.BOUTIQUE_NAME), 404

    @app.errorhandler(500)
    def internal_error(e):
        log.error("500 Internal Server Error | error=%s", str(e))
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Internal server error."}), 500
        return jsonify({"success": False, "error": "Internal server error."}), 500

    @app.errorhandler(403)
    def forbidden(e):
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Access denied."}), 403
        return redirect(url_for("auth.login_page"))

    log.info("Application factory complete. Ready to serve requests.")
    return app


# ── Dev server entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    port = int(os.getenv("PORT", "5000"))
    application.run(host="0.0.0.0", port=port, debug=get_config().DEBUG)
