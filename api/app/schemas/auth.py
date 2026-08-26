"""Auth schemas."""

import uuid

from pydantic import BaseModel

from app.models import UserRole


class LoginIn(BaseModel):
    # Plain str, not EmailStr: the demo logins are @demo.local by design, which
    # strict email validation rejects. Unknown emails simply fail login (401).
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: UserRole
