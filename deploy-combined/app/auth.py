"""Real, session-based auth for the multi-user Master Data Request flow
(submit as one user, log off, log in as a different user, approve from
the Review Queue). Opaque server-side session tokens (user_sessions),
not JWTs — the whole point of "real login with sessions" over a JWT is
that /auth/logout can actually revoke a session rather than the client
just discarding a self-contained token that stays valid until it expires.

Password hashing is stdlib PBKDF2-HMAC-SHA256, not a new dependency
(passlib/bcrypt) — this is a handful of internal demo users, not a
public-facing signup surface, and stdlib `hashlib` is already
constant-time-safe to compare via `hmac.compare_digest`.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import User, UserSession

SESSION_TTL = timedelta(hours=12)
_PBKDF2_ITERATIONS = 260_000


class InvalidCredentialsError(ValueError):
    """Username doesn't exist or password doesn't match — deliberately
    the same error either way, so a login form never reveals which
    usernames are valid."""


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, _, _ = stored_hash.partition("$")
    if not salt:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


def authenticate(session: Session, username: str, password: str) -> User:
    user = session.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password.")
    return user


def create_session(session: Session, user: User) -> UserSession:
    record = UserSession(
        token=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + SESSION_TTL,
    )
    session.add(record)
    session.commit()
    return record


def get_user_for_token(session: Session, token: str) -> User | None:
    record = session.get(UserSession, token)
    if record is None:
        return None
    if record.expires_at < datetime.now(timezone.utc):
        session.delete(record)
        session.commit()
        return None
    return session.get(User, record.user_id)


def invalidate_session(session: Session, token: str) -> None:
    record = session.get(UserSession, token)
    if record is not None:
        session.delete(record)
        session.commit()
