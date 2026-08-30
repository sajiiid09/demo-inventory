"""Startup bootstrap tests — the "just run the backend" promise.

Starting the API creates the database, migrates it, and seeds the staff
logins. Every step has to be safe to run again on the next restart, so that
is what these tests check.
"""

import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from app import bootstrap
from app.config import settings
from app.models import User, UserRole
from app.security import verify_password
from app.seeds import DEMO_PASSWORD, DEMO_USERS, ensure_users


class TestEnsureDatabase:
    def test_creates_a_missing_database_then_leaves_it_alone(self, database):
        url = make_url(settings.database_url).set(
            database=f"microloan_boot_{uuid.uuid4().hex[:8]}"
        )
        maintenance = create_engine(
            url.set(database="postgres").render_as_string(hide_password=False),
            isolation_level="AUTOCOMMIT",
        )
        try:
            assert bootstrap.ensure_database(url) is True   # first boot creates it
            assert bootstrap.ensure_database(url) is False  # second boot is a no-op
            with maintenance.connect() as conn:
                assert conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": url.database},
                )
        finally:
            with maintenance.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            maintenance.dispose()

    def test_existing_database_is_not_recreated(self, database):
        url = make_url(settings.database_url)
        assert bootstrap.ensure_database(url) is False


class TestMigrations:
    def test_upgrade_is_idempotent_and_reports_the_revision(self, database):
        # The session fixture already migrated; running it again must be a no-op.
        assert bootstrap.run_migrations() == "0001"
        assert bootstrap.run_migrations() == "0001"

    def test_every_table_exists_after_migrating(self, db):
        present = set(
            db.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            )
        )
        assert {
            "users", "members", "loans", "installments", "repayments",
            "repayment_allocations", "ledger_entries", "audit_log",
        } <= present


class TestEnsureUsers:
    def test_all_three_roles_are_seeded(self, db):
        seeded = {email: role for email, _, role in DEMO_USERS}
        for email, role in seeded.items():
            user = db.scalar(select(User).where(User.email == email))
            assert user is not None, f"{email} was not seeded"
            assert user.role is role
            assert user.is_active
        assert {role for role in seeded.values()} == set(UserRole)

    def test_repairs_a_drifted_account_without_duplicating_it(self, db):
        admin = db.scalar(select(User).where(User.email == "admin@demo.local"))
        admin.is_active = False
        admin.role = UserRole.CASHIER
        admin.full_name = "Changed During A Demo"
        db.commit()

        ensure_users(db)

        db.refresh(admin)
        assert admin.is_active is True
        assert admin.role is UserRole.ADMIN
        assert admin.full_name == "Ayesha Rahman"
        assert verify_password(DEMO_PASSWORD, admin.password_hash)
        assert db.scalar(
            select(User).where(User.email == "admin@demo.local").with_only_columns(User.id)
        ) is not None
        assert len(db.scalars(select(User)).all()) == len(DEMO_USERS)
