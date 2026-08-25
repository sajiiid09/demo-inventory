"""Auth endpoints: login (sets the httpOnly cookie), logout, me."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_session
from app.errors import unauthenticated
from app.models import User
from app.schemas.auth import LoginIn, UserOut
from app.security import (
    clear_session_cookie,
    create_access_token,
    get_current_user,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_BAD_CREDENTIALS = "Invalid email or password."  # identical for both failures


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        # Same message for unknown email and wrong password — no user enumeration.
        raise unauthenticated(_BAD_CREDENTIALS)
    if not user.is_active:
        raise unauthenticated(_BAD_CREDENTIALS)

    set_session_cookie(response, create_access_token(user))
    audit.record(
        session,
        actor_id=user.id,
        action=audit.USER_LOGGED_IN,
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
    return user


@router.post("/logout")
def logout(response: Response, user: User = Depends(get_current_user)):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
