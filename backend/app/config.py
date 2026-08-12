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

    # Microsoft Foundry (Azure AI Agents) project used by the Compare summary
    # agent. Auth is via DefaultAzureCredential (az login, or an
    # AZURE_CLIENT_ID/AZURE_CLIENT_SECRET/AZURE_TENANT_ID service principal) —
    # there's no key setting here because Foundry Agents doesn't take a raw
    # API key. Left unset in dev until a project exists; the agent module
    # degrades to a clear "not configured" error rather than failing at import.
    foundry_project_endpoint: str | None = None
    foundry_model_deployment: str = "gpt-4o-mini"


settings = Settings()
