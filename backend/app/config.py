from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Databricks Lakebase connection string (Postgres wire-compatible) —
    # see SETUP.md. Also hosts the relationship graph (relationship_edges
    # table, app/graph.py) — no separate graph database. Deliberately has
    # no password: native Postgres password auth is disabled on this
    # Lakebase project (Databricks itself warns it exposes the DB to the
    # open internet), so the only supported credential is a short-lived
    # OAuth token, fetched per-connection in app/lakebase_auth.py rather
    # than embedded here.
    database_url: str
    backend_port: int = 8000

    # Service principal used as the backend's own Databricks identity for
    # minting Lakebase OAuth tokens (client_credentials grant) — see
    # app/lakebase_auth.py. Not needed if database_url points at a
    # non-Lakebase Postgres instance.
    databricks_host: str | None = None
    databricks_client_id: str | None = None
    databricks_client_secret: str | None = None

    # Anthropic API key used by all Relsun agents (Compare summary today,
    # the Master Data agent hierarchy next — see the Agent Architecture
    # Pivot addendum in CONFIGURABLE_WORKFLOWS_AGENTS.md). Left unset in dev
    # until a real key is provisioned; agent modules degrade to a clear
    # "not configured" error rather than failing at import.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"


settings = Settings()
