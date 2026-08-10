from sqlalchemy import create_engine, text

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def check_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
