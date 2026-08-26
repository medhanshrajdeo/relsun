"""Seed the two demo users used to exercise the multi-user Master Data
Request flow: one logs in and submits a request, logs off, the other logs
in and sees it waiting in the Review Queue to approve/reject.

Not real accounts to be handed out to production users — this is a
prototype's fixed demo roster, matching the credentials printed on the
login page. Idempotent: re-running updates the password/display fields on
existing usernames rather than erroring or duplicating rows.

Run from backend/ with: python -m scripts.seed_users
"""

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import engine
from app.models import User

DEMO_USERS = [
    {"username": "alice", "display_name": "Alice", "role": "Sales Rep", "password": "alice123"},
    {"username": "bob", "display_name": "Bob", "role": "Data Steward", "password": "bob123"},
]


def main() -> None:
    with Session(engine) as session:
        for spec in DEMO_USERS:
            user = session.query(User).filter(User.username == spec["username"]).first()
            if user is None:
                user = User(username=spec["username"])
                session.add(user)
            user.display_name = spec["display_name"]
            user.role = spec["role"]
            user.password_hash = hash_password(spec["password"])
        session.commit()

    print(f"Seeded {len(DEMO_USERS)} demo users: {', '.join(u['username'] for u in DEMO_USERS)}")


if __name__ == "__main__":
    main()
