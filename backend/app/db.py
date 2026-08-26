from sqlalchemy import create_engine, event, text

from app.config import settings
from app.lakebase_auth import get_lakebase_token

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Recycle connections well before the ~1 hour Lakebase OAuth token
    # expiry (see lakebase_auth.py) — a pooled connection stays validly
    # authenticated past its token's expiry since Postgres doesn't
    # re-check the password mid-session, but we don't want connections
    # sitting in the pool indefinitely on a token that's long dead either.
    pool_recycle=1800,
)


@event.listens_for(engine, "do_connect")
def _inject_lakebase_token(dialect, conn_rec, cargs, cparams):
    if settings.databricks_client_id:
        cparams["password"] = get_lakebase_token()


def check_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
