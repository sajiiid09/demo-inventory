"""Passwords (argon2id) and sessions (JWT in an httpOnly cookie) — ADR-007.

FastAPI is the sole authority: every endpoint re-verifies the token and
re-checks the role. The frontend's middleware is a UX convenience only.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import ApiError, forbidden, unauthenticated
from app.models import User, UserRole

COOKIE_NAME = "access_token"
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(hours=settings.session_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise unauthenticated()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthenticated("Session is invalid or expired.")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthenticated("Session is invalid or expired.")
    return user


def require_role(*roles: UserRole):
    """Dependency factory. `require_role(ADMIN)` checks a role;
    `require_role()` with no roles means any authenticated user."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise forbidden(
                f"This action requires role {' or '.join(r.value for r in roles)}; "
                f"you are {user.role.value}."
            )
        return user

    return checker
