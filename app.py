"""
app.py - Infinity Designer Boutique Management System.

Full-stack Flask application: JSON REST API + Jinja2 HTML templates (PWA).

Run (development):
    python app.py

Run (production via Gunicorn):
    gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
"""
from __future__ import annotations

import os

from flask import Flask, jsonify, request, session
from flask_cors import CORS

from config import get_config, Config
from utils.logger import init_logging, get_logger

# -- Module imports ------------------------------------------------------------
from modules.auth.routes import auth_bp
from modules.users.routes import users_bp
from modules.attendance.routes import attendance_bp
from modules.financial.routes import financial_bp
from modules.overtime.routes import overtime_bp
from modules.settlements.routes import settlements_bp
from modules.dashboard.routes import dashboard_bp
from modules.settings.routes import settings_bp
from modules.leave.routes import leave_bp
from modules.pages.routes import pages_bp


def create_app(config: Config | None = None) -> Flask:
    """
    Application factory.

    Parameters
    ----------
    config : Optional Config instance.  Defaults to environment-detected config.
    """
    cfg = config or get_config()

    # -- Logging first (before anything else) ---------------------------------
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

    # -- Create Flask app with templates and static files ----------------------
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
        static_url_path="/static",
    )

    # -- Apply config ----------------------------------------------------------
    app.secret_key = cfg.SECRET_KEY
    app.config["DEBUG"] = cfg.DEBUG
    app.config["PERMANENT_SESSION_LIFETIME"] = cfg.PERMANENT_SESSION_LIFETIME
    app.config["SESSION_COOKIE_HTTPONLY"] = cfg.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = cfg.SESSION_COOKIE_SAMESITE
    app.config["BOUTIQUE_NAME"] = cfg.BOUTIQUE_NAME
    app.config["TIMEZONE"] = cfg.TIMEZONE
    app.config["DESIGNATIONS"] = cfg.DESIGNATIONS
    app.config["DESIGNATION_LABELS"] = cfg.DESIGNATION_LABELS
    # Authentication is handled exclusively via server-side Flask sessions.
    # JWT config has been removed as it was unused throughout the codebase.

    # -- CORS ------------------------------------------------------------------
    CORS(
        app,
        supports_credentials=True,
        origins=cfg.CORS_ORIGINS,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    log.info("CORS origins: %s", cfg.CORS_ORIGINS)

    # -- Initialise DB provider (firebase by default) --------------------------
    db_provider = os.getenv("APP_DB_PROVIDER", "firebase").strip().lower()
    if db_provider == "firebase":
        try:
            from utils.firebase_client import get_firestore
            get_firestore()
            log.info("Firebase / Firestore connected successfully.")
        except Exception as exc:  # noqa: BLE001
            log.error("Firebase initialisation failed: %s", exc)
            log.warning("App will start, but DB operations will fail until Firebase is configured.")
    else:
        log.info("DB provider selected: %s (firebase eager init skipped)", db_provider)

    # -- Register API blueprints -----------------------------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(financial_bp)
    app.register_blueprint(overtime_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(leave_bp)
    # Receipt upload blueprint removed

    # -- Register page-serving blueprint ---------------------------------------
    app.register_blueprint(pages_bp)

    log.info(
        "Blueprints registered: auth, users, attendance, financial, "
        "overtime, settlements, dashboard, settings, leave, pages"
    )

    # -- Request / response logging --------------------------------------------
    @app.before_request
    def log_incoming_request():
        if request.path == "/api/health" or request.path.startswith("/static"):
            return
        log.info(
            "REQUEST %s %s | ip=%s | user=%s",
            request.method,
            request.path,
            request.remote_addr,
            session.get("user_id", "anon"),
        )

    @app.after_request
    def log_outgoing_response(response):
        if request.path == "/api/health" or request.path.startswith("/static"):
            return response
        log.info(
            "RESPONSE %s %s | status=%d | user=%s",
            request.method,
            request.path,
            response.status_code,
            session.get("user_id", "anon"),
        )
        return response

    # -- Global error handlers (JSON for API, redirect for pages) --------------
    @app.errorhandler(404)
    def not_found(e):
        log.warning("404 Not Found | path=%s", request.path)
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found."}), 404
        return jsonify({"success": False, "error": "Page not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        log.warning("405 Method Not Allowed | path=%s | method=%s", request.path, request.method)
        return jsonify({"success": False, "error": "Method not allowed."}), 405

    @app.errorhandler(500)
    def internal_error(e):
        log.error("500 Internal Server Error | error=%s", str(e))
        return jsonify({"success": False, "error": "Internal server error."}), 500

    @app.errorhandler(403)
    def forbidden(e):
        log.warning("403 Forbidden | path=%s", request.path)
        return jsonify({"success": False, "error": "Access denied."}), 403

    @app.errorhandler(400)
    def bad_request(e):
        log.warning("400 Bad Request | path=%s | error=%s", request.path, str(e))
        return jsonify({"success": False, "error": "Bad request."}), 400

    # -- Health check ----------------------------------------------------------
    @app.get("/api/health")
    def health_check():
        return jsonify({"success": True, "status": "healthy", "app": cfg.BOUTIQUE_NAME})

    log.info("Application factory complete. Ready to serve requests.")
    return app


# -- Dev server entry point ----------------------------------------------------
if __name__ == "__main__":
    application = create_app()
    port = int(os.getenv("PORT", "5000"))
    application.run(host="0.0.0.0", port=port, debug=get_config().DEBUG)
