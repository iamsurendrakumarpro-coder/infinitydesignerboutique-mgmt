"""PostgreSQL connection helper utilities."""
from __future__ import annotations

import os

import psycopg2


def get_postgres_connection() -> psycopg2.extensions.connection:
    """Create a new PostgreSQL connection from environment variables."""
    host = os.getenv("POSTGRES_HOST", "").strip()
    port = int(os.getenv("POSTGRES_PORT", "5432").strip() or "5432")
    dbname = os.getenv("POSTGRES_DB", "").strip()
    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "").strip()

    if not host or not dbname or not user or not password:
        missing = [
            name
            for name, value in (
                ("POSTGRES_HOST", host),
                ("POSTGRES_DB", dbname),
                ("POSTGRES_USER", user),
                ("POSTGRES_PASSWORD", password),
            )
            if not value
        ]
        raise ValueError(f"Missing PostgreSQL environment variables: {', '.join(missing)}")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
