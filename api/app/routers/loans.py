"""Loan endpoints. POST /loans/preview is a pure calculation — it writes nothing."""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import clock
from app.db import get_session
from app.domain.penalty import InstallmentSnapshot, fee_outstanding
from app.domain.schedule import build_schedule, compute_terms
from app.models import (
    Installment,
    Loan,
    LoanFrequency,
    LoanStatus,
    RepaymentAllocation,
    User,
    UserRole,
)
from app.pagination import clamp
from app.schemas.common import Page
from app.schemas.loans import (
    AllocationMini,
    DisburseIn,
    LoanCreateIn,
    LoanDatesOut,
    LoanDetail,
    LoanListItem,
    LoanPreviewIn,
    LoanPreviewOut,
    LoanRejectIn,
    LoanTermsOut,
    LoanTotalsOut,
    MemberMini,
    PeopleOut,
    ScheduleDetailRow,
    ScheduleRowOut,
)
from app.schemas.repayments import SettlementQuoteOut
from app.services import loan_service, repayment_service
from app.services.helpers import outstanding_by_loan
from app.security import require_role

router = APIRouter(prefix="/loans", tags=["loans"])

ZERO = Decimal("0.00")


@router.post("/preview", response_model=LoanPreviewOut)
def preview(
    body: LoanPreviewIn,
    user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
):
    terms = compute_terms(
        body.principal, body.interest_rate_annual, body.term_count, body.frequency.value
    )
    rows = build_schedule(
        body.principal,
        body.interest_rate_annual,
        body.term_count,
        body.frequency.value,
        body.start_date,
    )
    return LoanPreviewOut(
        principal=body.principal,
        total_interest=terms.total_interest,
        total_payable=terms.total_payable,
        installment_amount=terms.installment_amount,
        schedule=[
            ScheduleRowOut(
                seq=r.seq, due_date=r.due_date, principal_due=r.principal_due,
                interest_due=r.interest_due, amount_due=r.amount_due,
            )
            for r in rows
        ],
    )


@router.post("", response_model=LoanDetail, status_code=201)
def create_loan(
    body: LoanCreateIn,
    user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    loan = loan_service.create(
        session,
        member_id=body.member_id,
        principal=body.principal,
        interest_rate_annual=body.interest_rate_annual,
        term_count=body.term_count,
        frequency=body.frequency.value,
        late_fee=body.late_fee,
        grace_days=body.grace_days,
        applied_on=body.applied_on,
        actor=user,
    )
    return _detail(session, loan, as_of=clock.today())


@router.get("", response_model=Page[LoanListItem])
def list_loans(
    status: LoanStatus | None = None,
    member_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    page, page_size = clamp(page, page_size)
    loans, total = loan_service.list_loans(
        session, status=status, member_id=member_id, q=q, page=page, page_size=page_size
    )
    outstanding = outstanding_by_loan(session, [loan.id for loan in loans])
    items = [
        LoanListItem(
            id=loan.id,
            loan_code=loan.loan_code,
            member=MemberMini(
                id=loan.member_id,
                member_code=loan.member.member_code,
                full_name=loan.member.full_name,
            ),
            principal=loan.principal,
            status=loan.status,
            total_payable=loan.total_payable,
            outstanding=outstanding.get(loan.id, ZERO),
            next_due_date=_next_due_date(session, loan.id),
        )
        for loan in loans
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


def _next_due_date(session: Session, loan_id: uuid.UUID) -> dt.date | None:
    return session.scalar(
        select(func.min(Installment.due_date)).where(
            Installment.loan_id == loan_id,
            Installment.amount_due - Installment.principal_paid - Installment.interest_paid > 0,
        )
    )


@router.get("/{loan_id}", response_model=LoanDetail)
def get_loan(
    loan_id: uuid.UUID,
    as_of: dt.date | None = None,
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    loan = loan_service.get(session, loan_id)
    return _detail(session, loan, as_of or clock.today())


@router.post("/{loan_id}/approve", response_model=LoanDetail)
def approve_loan(
    loan_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    loan = loan_service.approve(session, loan_id=loan_id, actor=user)
    return _detail(session, loan, as_of=clock.today())


@router.post("/{loan_id}/reject", response_model=LoanDetail)
def reject_loan(
    loan_id: uuid.UUID,
    body: LoanRejectIn,
    user: User = Depends(require_role(UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    loan = loan_service.reject(session, loan_id=loan_id, reason=body.reason, actor=user)
    return _detail(session, loan, as_of=clock.today())


@router.post("/{loan_id}/disburse", response_model=LoanDetail)
def disburse_loan(
    loan_id: uuid.UUID,
    body: DisburseIn,
    user: User = Depends(require_role(UserRole.CASHIER, UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    loan = loan_service.disburse(
        session, loan_id=loan_id, disbursed_on=body.disbursed_on, actor=user
    )
    return _detail(session, loan, as_of=clock.today())


@router.get("/{loan_id}/settlement-quote", response_model=SettlementQuoteOut)
def settlement_quote(
    loan_id: uuid.UUID,
    as_of: dt.date | None = None,
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    # Flat interest: no rebate. Settling early costs remaining amount_due plus
    # accrued fees as of `as_of` (DOMAIN.md §10).
    outstanding, fees, total, _loan = repayment_service.settlement_quote(
        session, loan_id=loan_id, as_of=as_of or clock.today()
    )
    return SettlementQuoteOut(
        as_of=as_of or clock.today(),
        outstanding=outstanding,
        accrued_fees=fees,
        settlement_total=total,
    )


# --- detail assembly ---------------------------------------------------------


def _person(user_obj) -> str | None:
    if user_obj is None:
        return None
    return f"{user_obj.full_name} ({user_obj.role.value})"


def _detail(session: Session, loan: Loan, as_of: dt.date) -> LoanDetail:
    installments = loan_service.installments_for(session, loan.id)

    snapshots = {
        i.seq: InstallmentSnapshot(
            seq=i.seq,
            due_date=i.due_date,
            principal_due=i.principal_due,
            interest_due=i.interest_due,
            amount_due=i.amount_due,
            principal_paid=i.principal_paid,
            interest_paid=i.interest_paid,
            fee_paid=i.fee_paid,
        )
        for i in installments
    }

    allocations: dict[uuid.UUID, list[AllocationMini]] = {}
    if installments:
        rows = session.execute(
            select(RepaymentAllocation, Installment.seq)
            .join(Installment, RepaymentAllocation.installment_id == Installment.id)
            .where(Installment.loan_id == loan.id)
            .options(joinedload(RepaymentAllocation.repayment))
            .order_by(Installment.seq)
        ).all()
        for alloc, seq in rows:
            allocations.setdefault(seq, []).append(
                AllocationMini(
                    receipt_no=alloc.repayment.receipt_no,
                    fee=alloc.fee_amount,
                    interest=alloc.interest_amount,
                    principal=alloc.principal_amount,
                )
            )

    schedule_rows = []
    paid_total = ZERO
    outstanding_total = ZERO
    accrued_fees_total = ZERO
    for inst in installments:
        snap = snapshots[inst.seq]
        paid = inst.principal_paid + inst.interest_paid
        row_status = "PAID" if paid >= inst.amount_due else ("PARTIAL" if paid > 0 else "PENDING")
        fee_owed = fee_outstanding(snap, loan.late_fee, loan.grace_days, as_of)
        paid_total += paid + inst.fee_paid
        outstanding_total += inst.amount_due - paid
        accrued_fees_total += fee_owed
        schedule_rows.append(
            ScheduleDetailRow(
                seq=inst.seq,
                due_date=inst.due_date,
                principal_due=inst.principal_due,
                interest_due=inst.interest_due,
                amount_due=inst.amount_due,
                principal_paid=inst.principal_paid,
                interest_paid=inst.interest_paid,
                fee_paid=inst.fee_paid,
                status=row_status,
                accrued_fee=fee_owed,
                allocations=allocations.get(inst.seq, []),
            )
        )

    return LoanDetail(
        id=loan.id,
        loan_code=loan.loan_code,
        status=loan.status,
        member=MemberMini(
            id=loan.member.id,
            member_code=loan.member.member_code,
            full_name=loan.member.full_name,
        ),
        terms=LoanTermsOut(
            principal=loan.principal,
            interest_rate_annual=loan.interest_rate_annual,
            term_count=loan.term_count,
            frequency=loan.frequency,
            late_fee=loan.late_fee,
            grace_days=loan.grace_days,
        ),
        totals=LoanTotalsOut(
            total_interest=loan.total_interest,
            total_payable=loan.total_payable,
            installment_amount=loan.installment_amount,
            paid_total=paid_total,
            outstanding=outstanding_total,
            accrued_fees=accrued_fees_total,
        ),
        dates=LoanDatesOut(
            applied_on=loan.applied_on,
            approved_at=loan.approved_at,
            disbursed_on=loan.disbursed_on,
            closed_at=loan.closed_at,
        ),
        people=PeopleOut(
            created_by=_person(loan.creator) or "?",
            approved_by=_person(loan.approver),
            disbursed_by=_person(loan.disbursor),
        ),
        schedule=schedule_rows,
    )
