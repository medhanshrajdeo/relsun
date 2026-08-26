from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_user_for_token
from app.db import engine
from app.models import User


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_bearer_token(x_relsun_token: str | None = Header(default=None)) -> str:
    # Deliberately not the standard `Authorization` header: Databricks Apps'
    # own gateway reserves that header for its own OAuth session validation
    # and strips/rejects anything it can't validate as a Databricks token
    # before the request ever reaches this app — discovered live when every
    # authenticated call 401'd with no Authorization header visible here at
    # all, even immediately after a successful login on the same origin.
    if not x_relsun_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_relsun_token.strip()


def get_current_user(
    token: str = Depends(get_bearer_token),
    session: Session = Depends(get_session),
) -> User:
    user = get_user_for_token(session, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again.")
    return user
