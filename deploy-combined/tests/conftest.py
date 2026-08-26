"""
db_session: a real Postgres session (same dev DB the app uses) wrapped in
an outer transaction + SAVEPOINT, so every test's writes — including any
session.commit() calls inside app code — roll back at teardown. Nothing
persists; the 3.4M-row GLEIF dataset never gets touched.
"""

import pytest
from sqlalchemy.orm import Session

from app.db import engine


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
