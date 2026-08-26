"""Test bootstrap.

A throwaway `microloan_test` database is created and migrated once per
session. Tests build their own world through the API (unique phones/national
IDs per test) and never call date.today() — every date is fixed, and R5's
"not in the future" guard reads the injectable app clock.
"""

import os
import uuid

TEST_DB = "microloan_test"
TEST_DATABASE_URL = f"postgresql+psycopg://microloan:microloan@localhost:5433/{TEST_DB}"

# Must happen before ANY app module import — settings read the env once.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_USERS = [
    ("admin@demo.local", "Ayesha Rahman", UserRole.ADMIN),
    ("officer@demo.local", "Karim Hussain", UserRole.OFFICER),
    ("cashier@demo.local", "Nadia Islam", UserRole.CASHIER),
]


@pytest.fixture(scope="session", autouse=True)
def database():
    """Fresh throwaway database, migrated, with the three demo users."""
    admin_conn = psycopg.connect(
        "host=localhost port=5433 dbname=microloan user=microloan password=microloan",
        autocommit=True,
    )
    admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    admin_conn.execute(f"CREATE DATABASE {TEST_DB}")
    admin_conn.close()

    alembic_cfg = Config("alembic.ini")  # env.py reads DATABASE_URL from settings
    command.upgrade(alembic_cfg, "head")

    with SessionLocal() as session:
        for email, full_name, role in DEMO_USERS:
            session.add(
                User(
                    email=email, full_name=full_name, role=role,
                    password_hash=hash_password("demo1234"),
                )
            )
        session.commit()
    yield


@pytest.fixture(scope="session")
def clients(database):
    """One logged-in TestClient per role."""

    class Clients:
        pass

    bundle = Clients()
    for role in ("admin", "officer", "cashier"):
        client = TestClient(app)
        response = client.post(
            "/auth/login",
            json={"email": f"{role}@demo.local", "password": "demo1234"},
        )
        assert response.status_code == 200, response.text
        setattr(bundle, role, client)
    return bundle


@pytest.fixture()
def db():
    """A direct session for asserting on committed state."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def unique(**overrides) -> dict:
    """A member payload that can never collide with another test's data."""
    suffix = uuid.uuid4().hex[:10]
    payload = {
        "full_name": f"Test Person {suffix}",
        "phone": f"017{suffix[:8]}",
        "national_id": f"NID{suffix}",
        "address": "Test Address",
        "joined_on": "2026-01-02",
    }
    payload.update(overrides)
    return payload


def make_member(clients, **overrides) -> dict:
    response = clients.officer.post("/members", json=unique(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def make_loan(
    clients,
    *,
    principal="100000.00",
    rate="12.00",
    term=24,
    frequency="WEEKLY",
    late_fee="100.00",
    grace_days=3,
    by="officer",
) -> dict:
    """member → PENDING loan → APPROVED (admin) → DISBURSED (cashier)."""
    member = make_member(clients)
    client = getattr(clients, by)
    response = client.post(
        "/loans",
        json={
            "member_id": member["id"],
            "principal": principal,
            "interest_rate_annual": rate,
            "term_count": term,
            "frequency": frequency,
            "late_fee": late_fee,
            "grace_days": grace_days,
            "applied_on": "2026-01-02",
        },
    )
    assert response.status_code == 201, response.text
    loan = response.json()

    approve = clients.admin.post(f"/loans/{loan['id']}/approve")
    assert approve.status_code == 200, approve.text

    disburse = clients.cashier.post(
        f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-05"}
    )
    assert disburse.status_code == 200, disburse.text
    return disburse.json()
