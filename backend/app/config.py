from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    backend_port: int = 8000

    # Anthropic API key used by all Relsun agents (Compare summary today,
    # the Master Data agent hierarchy next — see the Agent Architecture
    # Pivot addendum in CONFIGURABLE_WORKFLOWS_AGENTS.md). Left unset in dev
    # until a real key is provisioned; agent modules degrade to a clear
    # "not configured" error rather than failing at import.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"


settings = Settings()
