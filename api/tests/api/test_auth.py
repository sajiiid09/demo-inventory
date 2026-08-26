"""Auth boundary tests — TESTING.md §3 (rules-focused subset)."""

import datetime as dt
import uuid

import jwt as pyjwt
from fastapi.testclient import TestClient

from app.config import settings
from app.models import AuditLog
from app.main import app


class TestAuth:
    def test_login_sets_httponly_cookie(self, clients):
        fresh = TestClient(app)
        response = fresh.post(
            "/auth/login", json={"email": "admin@demo.local", "password": "demo1234"}
        )
        assert response.status_code == 200
        set_cookie = response.headers["set-cookie"]
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "samesite=lax" in set_cookie.lower()

    def test_login_with_wrong_password_returns_401(self, database):
        fresh = TestClient(app)
        response = fresh.post(
            "/auth/login", json={"email": "admin@demo.local", "password": "nope"}
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "UNAUTHENTICATED"

    def test_login_of_unknown_user_returns_same_message(self, database):
        fresh = TestClient(app)
        wrong_password = fresh.post(
            "/auth/login", json={"email": "admin@demo.local", "password": "nope"}
        )
        unknown_email = fresh.post(
            "/auth/login", json={"email": "ghost@nowhere.local", "password": "nope"}
        )
        # identical messages — the endpoint cannot be used to discover emails
        assert wrong_password.json() == unknown_email.json()

    def test_request_without_cookie_returns_401(self, database):
        fresh = TestClient(app)
        response = fresh.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "UNAUTHENTICATED"

    def test_expired_token_returns_401(self, database):
        token = pyjwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "role": "ADMIN",
                "exp": int(
                    (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).timestamp()
                ),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        fresh = TestClient(app)
        fresh.cookies.set("access_token", token)
        response = fresh.get("/auth/me")
        assert response.status_code == 401

    def test_me_returns_current_user_and_role(self, clients):
        response = clients.officer.get("/auth/me")
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "officer@demo.local"
        assert body["role"] == "OFFICER"

    def test_login_writes_an_audit_row(self, db):
        fresh = TestClient(app)
        fresh.post(
            "/auth/login",
            json={"email": "cashier@demo.local", "password": "demo1234"},
        )
        row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "USER_LOGGED_IN")
            .order_by(AuditLog.occurred_at.desc())
            .first()
        )
        assert row is not None
        assert row.entity_type == "user"
