"""Loan schemas — API.md §5."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models import LoanFrequency, LoanStatus
from app.schemas.common import Money


class LoanPreviewIn(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    interest_rate_annual: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    term_count: int = Field(gt=0, le=120)
    frequency: LoanFrequency
    start_date: date


class ScheduleRowOut(BaseModel):
    seq: int
    due_date: date
    principal_due: Money
    interest_due: Money
    amount_due: Money


class LoanPreviewOut(BaseModel):
    principal: Money
    total_interest: Money
    total_payable: Money
    installment_amount: Money
    schedule: list[ScheduleRowOut]


class LoanCreateIn(BaseModel):
    member_id: uuid.UUID
    principal: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    interest_rate_annual: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    term_count: int = Field(gt=0, le=120)
    frequency: LoanFrequency
    late_fee: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    grace_days: int = Field(default=3, ge=0, le=30)
    applied_on: date


class LoanRejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DisburseIn(BaseModel):
    disbursed_on: date


class MemberMini(BaseModel):
    id: uuid.UUID
    member_code: str
    full_name: str


class LoanListItem(BaseModel):
    id: uuid.UUID
    loan_code: str
    member: MemberMini
    principal: Money
    status: LoanStatus
    total_payable: Money | None
    outstanding: Money
    next_due_date: date | None


class LoanTermsOut(BaseModel):
    principal: Money
    interest_rate_annual: Money
    term_count: int
    frequency: LoanFrequency
    late_fee: Money
    grace_days: int


class LoanTotalsOut(BaseModel):
    total_interest: Money | None
    total_payable: Money | None
    installment_amount: Money | None
    paid_total: Money
    outstanding: Money
    accrued_fees: Money


class LoanDatesOut(BaseModel):
    applied_on: date
    approved_at: datetime | None
    disbursed_on: date | None
    closed_at: datetime | None


class PeopleOut(BaseModel):
    created_by: str
    approved_by: str | None = None
    disbursed_by: str | None = None


class AllocationMini(BaseModel):
    receipt_no: str
    fee: Money
    interest: Money
    principal: Money


class ScheduleDetailRow(BaseModel):
    seq: int
    due_date: date
    principal_due: Money
    interest_due: Money
    amount_due: Money
    principal_paid: Money
    interest_paid: Money
    fee_paid: Money
    status: str  # PENDING | PARTIAL | PAID — computed, not stored
    accrued_fee: Money  # fee still owed as of `as_of` — computed, not stored
    allocations: list[AllocationMini]


class LoanDetail(BaseModel):
    id: uuid.UUID
    loan_code: str
    status: LoanStatus
    member: MemberMini
    terms: LoanTermsOut
    totals: LoanTotalsOut
    dates: LoanDatesOut
    people: PeopleOut
    schedule: list[ScheduleDetailRow]
