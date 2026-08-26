"""Mints short-lived Databricks OAuth tokens for Lakebase Postgres connections.

Native Postgres password auth is disabled on the relsun-db Lakebase project —
Databricks itself warns that enabling it exposes the database to the open
internet. OAuth (via the relsun-backend service principal, a
client_credentials grant) is the only supported native-Postgres credential
here, and tokens expire after ~1 hour, so a token can't just be embedded in
DATABASE_URL like a normal password. Instead app/db.py's `do_connect` hook
calls get_lakebase_token() on every new physical connection, and this module
caches the token in memory, refetching once it's within
_TOKEN_SAFETY_MARGIN_SECONDS of expiry.
"""

import time

import httpx

from app.config import settings

_TOKEN_SAFETY_MARGIN_SECONDS = 300

_cached_token: str | None = None
_cached_token_expiry: float = 0.0


def get_lakebase_token() -> str:
    global _cached_token, _cached_token_expiry

    now = time.monotonic()
    if _cached_token and now < _cached_token_expiry - _TOKEN_SAFETY_MARGIN_SECONDS:
        return _cached_token

    if not (settings.databricks_host and settings.databricks_client_id and settings.databricks_client_secret):
        raise RuntimeError(
            "DATABRICKS_HOST / DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET "
            "must be set in .env to connect to a Lakebase database with OAuth."
        )

    response = httpx.post(
        f"{settings.databricks_host}/oidc/v1/token",
        data={"grant_type": "client_credentials", "scope": "all-apis"},
        auth=(settings.databricks_client_id, settings.databricks_client_secret),
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    _cached_token = payload["access_token"]
    _cached_token_expiry = now + payload.get("expires_in", 3600)
    return _cached_token


def get_raw_dsn() -> str:
    """Plain psycopg DSN (no sqlalchemy+ prefix) with a fresh Lakebase OAuth
    token baked in as the password, for scripts that connect directly with
    psycopg — e.g. for COPY-based bulk loads — instead of going through
    app.db.engine's do_connect hook.
    """
    import psycopg.conninfo

    base = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    parsed = psycopg.conninfo.conninfo_to_dict(base)
    if settings.databricks_client_id:
        parsed["password"] = get_lakebase_token()
    return psycopg.conninfo.make_conninfo(**parsed)
