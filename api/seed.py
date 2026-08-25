"""Seed the demo database with the three staff users (phase 3).

Phase 9 grows this into the full demo dataset (members, loans in every status,
repayments). Run only on a fresh schema — the ledger is append-only, so
reseeding means `alembic downgrade base && alembic upgrade head` first.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User, UserRole
from app.security import hash_password

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("admin@demo.local", "Ayesha Rahman", UserRole.ADMIN),
    ("officer@demo.local", "Karim Hussain", UserRole.OFFICER),
    ("cashier@demo.local", "Nadia Islam", UserRole.CASHIER),
]


def seed() -> None:
    with SessionLocal() as session:
        existing = session.scalar(select(User).limit(1))
        if existing is not None:
            raise SystemExit(
                "Database already has data. To reseed from scratch:\n"
                "  alembic downgrade base && alembic upgrade head && python seed.py"
            )
        for email, full_name, role in DEMO_USERS:
            session.add(
                User(
                    email=email,
                    full_name=full_name,
                    role=role,
                    password_hash=hash_password(DEMO_PASSWORD),
                )
            )
        session.commit()
        print(f"Seeded {len(DEMO_USERS)} demo users (password: {DEMO_PASSWORD}).")


if __name__ == "__main__":
    seed()
