"""Test bootstrap.

A throwaway `microloan_test` database is created and migrated once per
session, on whatever Postgres DATABASE_URL points at — so the same suite runs
on the host (`cd api && pytest`) and inside the container
(`docker compose exec api pytest`). Tests build their own world through the API
(unique phones/national IDs per test) and never call date.today() — every date
is fixed, and R5's "not in the future" guard reads the injectable app clock.

The application's startup bootstrap is switched off here: this file owns the
test database, and the demo portfolio would only get in the tests' way.
"""

import os
import uuid

from sqlalchemy.engine import make_url

TEST_DB = "microloan_test"

# Must happen before ANY app module import — settings read the env once.
_source_url = make_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://microloan:123@localhost:5433/microloan",
    )
)
os.environ["DATABASE_URL"] = _source_url.set(database=TEST_DB).render_as_string(
    hide_password=False
)
os.environ["AUTO_MIGRATE"] = "false"
os.environ["AUTO_SEED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import bootstrap  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seeds import DEMO_PASSWORD, DEMO_USERS  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    """Fresh throwaway database, migrated, with the three demo users."""
    maintenance = create_engine(
        _source_url.set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    with maintenance.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    maintenance.dispose()

    bootstrap.run_migrations()  # the same upgrade the API runs on startup

    with SessionLocal() as session:
        for email, full_name, role in DEMO_USERS:
            session.add(
                User(
                    email=email, full_name=full_name, role=role,
                    password_hash=hash_password(DEMO_PASSWORD),
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
            json={"email": f"{role}@demo.local", "password": DEMO_PASSWORD},
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
