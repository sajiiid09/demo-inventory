"""Repayment endpoints — the receipt tells the customer exactly where their
money went: one line per installment touched, split fee / interest / principal."""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import PaymentMethod, User, UserRole
from app.pagination import clamp
from app.schemas.common import Page
from app.schemas.loans import MemberMini
from app.schemas.repayments import (
    AllocationOut,
    ReceiptOut,
    RepaymentCreateIn,
    RepaymentListItem,
)
from app.services import repayment_service
from app.services.helpers import outstanding_by_loan
from app.security import require_role

router = APIRouter(prefix="/repayments", tags=["repayments"])

ZERO = Decimal("0.00")


@router.post("", response_model=ReceiptOut, status_code=201)
def record_repayment(
    body: RepaymentCreateIn,
    user: User = Depends(require_role(UserRole.CASHIER, UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    repayment, plan, loan = repayment_service.record(
        session,
        loan_id=body.loan_id,
        amount=body.amount,
        paid_on=body.paid_on,
        method=body.method,
        note=body.note,
        actor=user,
    )
    lines = repayment_service.allocation_lines(session, repayment.id)
    outstanding = outstanding_by_loan(session, [loan.id]).get(loan.id, ZERO)
    return _receipt(repayment, loan, lines, loan.status, outstanding)


@router.get("", response_model=Page[RepaymentListItem])
def list_repayments(
    receipt_no: str | None = None,
    loan_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    from_date: dt.date | None = Query(None, alias="from"),
    to_date: dt.date | None = Query(None, alias="to"),
    method: PaymentMethod | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    page, page_size = clamp(page, page_size)
    repayments, total = repayment_service.list_repayments(
        session,
        receipt_no=receipt_no,
        loan_id=loan_id,
        member_id=member_id,
        date_from=from_date,
        date_to=to_date,
        method=method,
        page=page,
        page_size=page_size,
    )
    items = [
        RepaymentListItem(
            id=r.id,
            receipt_no=r.receipt_no,
            loan_code=r.loan.loan_code,
            member=MemberMini(
                id=r.loan.member.id,
                member_code=r.loan.member.member_code,
                full_name=r.loan.member.full_name,
            ),
            amount=r.amount,
            paid_on=r.paid_on,
            method=r.method,
        )
        for r in repayments
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{repayment_id}", response_model=ReceiptOut)
def get_repayment(
    repayment_id: uuid.UUID,
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    repayment = repayment_service.get(session, repayment_id)
    loan = repayment.loan
    lines = repayment_service.allocation_lines(session, repayment.id)
    outstanding = outstanding_by_loan(session, [loan.id]).get(loan.id, ZERO)
    return _receipt(repayment, loan, lines, loan.status, outstanding)


def _receipt(repayment, loan, lines, status_after, outstanding_after) -> ReceiptOut:
    return ReceiptOut(
        id=repayment.id,
        receipt_no=repayment.receipt_no,
        loan_code=loan.loan_code,
        member=MemberMini(
            id=loan.member.id,
            member_code=loan.member.member_code,
            full_name=loan.member.full_name,
        ),
        amount=repayment.amount,
        paid_on=repayment.paid_on,
        method=repayment.method,
        note=repayment.note,
        received_by=f"{repayment.receiver.full_name} ({repayment.receiver.role.value})",
        allocations=[
            AllocationOut(
                seq=seq, due_date=due, fee=fee, interest=interest,
                principal=principal,
                total=fee + interest + principal,
            )
            for seq, due, fee, interest, principal in lines
        ],
        loan_status_after=status_after,
        outstanding_after=outstanding_after,
    )
