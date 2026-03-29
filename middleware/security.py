"""
middleware/security.py - Enterprise security headers and protections.

Adds security headers to all responses:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HSTS)
- Content-Security-Policy (CSP)
- Referrer-Policy
- Permissions-Policy
- X-Request-ID for tracing
"""
from __future__ import annotations

from flask import Flask, request, g

from middleware.response import get_request_id
from utils.logger import get_logger

log = get_logger(__name__)


def init_security_headers(app: Flask) -> None:
    """Register after_request handler that injects security headers."""

    @app.after_request
    def add_security_headers(response):
        # Request ID for tracing
        response.headers["X-Request-ID"] = get_request_id()

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (restrict browser features)
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=()"
        )

        # HSTS (only on HTTPS)
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content-Security-Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.googleapis.com https://*.googleusercontent.com blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://*.googleapis.com; "
            "frame-ancestors 'none';"
        )

        return response

    log.info("Security headers middleware registered.")
