"""Repayment schemas — API.md §6."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import LoanStatus, PaymentMethod
from app.schemas.common import Money
from app.schemas.loans import MemberMini


class RepaymentCreateIn(BaseModel):
    loan_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    paid_on: date
    method: PaymentMethod
    note: str | None = Field(default=None, max_length=500)


class AllocationOut(BaseModel):
    seq: int
    due_date: date
    fee: Money
    interest: Money
    principal: Money
    total: Money


class ReceiptOut(BaseModel):
    id: uuid.UUID
    receipt_no: str
    loan_code: str
    member: MemberMini
    amount: Money
    paid_on: date
    method: PaymentMethod
    note: str | None
    received_by: str
    allocations: list[AllocationOut]
    loan_status_after: LoanStatus
    outstanding_after: Money


class RepaymentListItem(BaseModel):
    id: uuid.UUID
    receipt_no: str
    loan_code: str
    member: MemberMini
    amount: Money
    paid_on: date
    method: PaymentMethod


class SettlementQuoteOut(BaseModel):
    as_of: date
    outstanding: Money
    accrued_fees: Money
    settlement_total: Money
