"""Member schemas — API.md §4."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import LoanStatus, MemberStatus
from app.schemas.common import Money


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=4, max_length=30)
    national_id: str = Field(min_length=4, max_length=40)
    address: str | None = None
    joined_on: date


class MemberStatusIn(BaseModel):
    status: MemberStatus


class MemberListItem(BaseModel):
    id: uuid.UUID
    member_code: str
    full_name: str
    phone: str
    status: MemberStatus
    active_loan_code: str | None
    outstanding: Money


class MemberLoanSummary(BaseModel):
    id: uuid.UUID
    loan_code: str
    status: LoanStatus
    principal: Money
    outstanding: Money


class MemberDetail(BaseModel):
    id: uuid.UUID
    member_code: str
    full_name: str
    phone: str
    national_id: str
    address: str | None
    joined_on: date
    status: MemberStatus
    created_by: uuid.UUID
    created_at: datetime
    loans: list[MemberLoanSummary]
