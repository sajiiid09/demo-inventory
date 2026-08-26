"""The loan lifecycle — DOMAIN.md §2.

create → PENDING → approve (ADMIN, never the creator — R1) → APPROVED
       → reject (ADMIN, reason)  → REJECTED ●
       → disburse (CASHIER/ADMIN) → DISBURSED → all rows paid → CLOSED ●

Disbursement is the first multi-table transaction: frozen totals, N installment
rows, a DISBURSEMENT ledger entry, and an audit row — all or nothing (R4).
"""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import audit, clock
from app.domain.schedule import ComputedTerms, build_schedule, compute_terms
from app.errors import ApiError, invalid_date, invalid_state, not_found
from app.models import (
    Installment,
    LedgerDirection,
    LedgerEntry,
    LedgerEntryType,
    Loan,
    LoanStatus,
    Member,
    MemberStatus,
    User,
)
from app.services.helpers import next_code

ZERO = Decimal("0.00")
ACTIVE_STATUSES = (LoanStatus.APPROVED, LoanStatus.DISBURSED)


def _load(session: Session, loan_id: uuid.UUID, *, for_update: bool = False) -> Loan:
    stmt = select(Loan).where(Loan.id == loan_id)
    if for_update:
        # Lock ONLY the loans row: eager-loaded users joins must not carry FOR UPDATE.
        stmt = stmt.with_for_update(of=Loan)
    loan = session.scalar(stmt)
    if loan is None:
        raise not_found("No loan with this id.")
    return loan


def _member_active_loan(session: Session, member_id: uuid.UUID) -> Loan | None:
    return session.scalar(
        select(Loan).where(Loan.member_id == member_id, Loan.status.in_(ACTIVE_STATUSES))
    )


# --- create ---------------------------------------------------------------


def create(
    session: Session,
    *,
    member_id: uuid.UUID,
    principal: Decimal,
    interest_rate_annual: Decimal,
    term_count: int,
    frequency: str,
    late_fee: Decimal,
    grace_days: int,
    applied_on: dt.date,
    actor: User,
) -> Loan:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("No member with this id.")
    if member.status != MemberStatus.ACTIVE:
        raise invalid_state(f"{member.member_code} is INACTIVE; new loans require an ACTIVE member.")

    # R2 — a member may hold only one APPROVED/DISBURSED loan. Two PENDING
    # applications may coexist; approving the second is what gets refused.
    active = _member_active_loan(session, member_id)
    if active is not None:
        raise ApiError(
            409,
            "MEMBER_HAS_ACTIVE_LOAN",
            f"Member {member.member_code} already has an active loan ({active.loan_code}).",
        )

    loan = Loan(
        loan_code=next_code(session, Loan.loan_code, "L-"),
        member_id=member_id,
        principal=principal,
        interest_rate_annual=interest_rate_annual,
        term_count=term_count,
        frequency=frequency,
        late_fee=late_fee,
        grace_days=grace_days,
        status=LoanStatus.PENDING,
        applied_on=applied_on,
        created_by=actor.id,
    )
    session.add(loan)
    session.flush()
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.LOAN_CREATED,
        entity_type="loan",
        entity_id=loan.id,
        after={"loan_code": loan.loan_code, "principal": str(principal), "status": "PENDING"},
    )
    session.commit()
    return loan


# --- approve / reject -------------------------------------------------------


def approve(session: Session, *, loan_id: uuid.UUID, actor: User) -> Loan:
    loan = _load(session, loan_id)
    if loan.status != LoanStatus.PENDING:
        raise invalid_state(
            f"Loan {loan.loan_code} is {loan.status.value}; only PENDING loans can be approved."
        )
    # R1 — the creator may never approve, ADMIN included.
    if loan.created_by == actor.id:
        raise ApiError(
            403,
            "FORBIDDEN_SELF_APPROVAL",
            f"You created {loan.loan_code}, so you cannot approve it (R1).",
        )
    # R2 again, at the moment it becomes binding.
    active = _member_active_loan(session, loan.member_id)
    if active is not None:
        raise ApiError(
            409,
            "MEMBER_HAS_ACTIVE_LOAN",
            f"Member already has an active loan ({active.loan_code}); "
            f"approving {loan.loan_code} would give them two (R2).",
        )

    loan.status = LoanStatus.APPROVED
    loan.approved_by = actor.id
    loan.approver = actor  # keep the in-memory object fresh for the response
    loan.approved_at = func.now()
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.LOAN_APPROVED,
        entity_type="loan",
        entity_id=loan.id,
        before={"status": "PENDING"},
        after={"status": "APPROVED", "approved_by": str(actor.id)},
    )
    session.commit()
    return loan


def reject(session: Session, *, loan_id: uuid.UUID, reason: str, actor: User) -> Loan:
    loan = _load(session, loan_id)
    if loan.status != LoanStatus.PENDING:
        raise invalid_state(
            f"Loan {loan.loan_code} is {loan.status.value}; only PENDING loans can be rejected."
        )
    loan.status = LoanStatus.REJECTED
    loan.rejection_reason = reason
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.LOAN_REJECTED,
        entity_type="loan",
        entity_id=loan.id,
        before={"status": "PENDING"},
        after={"status": "REJECTED", "reason": reason},
    )
    session.commit()
    return loan


# --- disburse ---------------------------------------------------------------


def disburse(
    session: Session, *, loan_id: uuid.UUID, disbursed_on: dt.date, actor: User
) -> Loan:
    loan = _load(session, loan_id, for_update=True)
    if loan.status != LoanStatus.APPROVED:
        raise invalid_state(
            f"Loan {loan.loan_code} is {loan.status.value}; only APPROVED loans can be disbursed."
        )
    # R5 — money cannot leave before it was applied for, nor in the future.
    if disbursed_on < loan.applied_on:
        raise invalid_date(
            f"disbursed_on ({disbursed_on}) precedes applied_on ({loan.applied_on}) (R5)."
        )
    if disbursed_on > clock.today():
        raise invalid_date(f"disbursed_on ({disbursed_on}) is in the future (R5).")

    # R4 — the three totals are computed ONCE here and frozen forever.
    terms: ComputedTerms = compute_terms(
        loan.principal, loan.interest_rate_annual, loan.term_count, loan.frequency.value
    )
    loan.total_interest = terms.total_interest
    loan.total_payable = terms.total_payable
    loan.installment_amount = terms.installment_amount
    loan.status = LoanStatus.DISBURSED
    loan.disbursed_on = disbursed_on
    loan.disbursed_by = actor.id

    for row in build_schedule(
        loan.principal,
        loan.interest_rate_annual,
        loan.term_count,
        loan.frequency.value,
        disbursed_on,
    ):
        session.add(
            Installment(
                loan_id=loan.id,
                seq=row.seq,
                due_date=row.due_date,
                principal_due=row.principal_due,
                interest_due=row.interest_due,
                amount_due=row.amount_due,
            )
        )

    session.add(
        LedgerEntry(
            entry_type=LedgerEntryType.DISBURSEMENT,
            direction=LedgerDirection.OUT,
            loan_id=loan.id,
            amount=loan.principal,
            occurred_on=disbursed_on,
            source_id=loan.id,
            created_by=actor.id,
        )
    )
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.LOAN_DISBURSED,
        entity_type="loan",
        entity_id=loan.id,
        before={"status": "APPROVED"},
        after={
            "status": "DISBURSED",
            "disbursed_on": str(disbursed_on),
            "total_payable": str(terms.total_payable),
            "installments": loan.term_count,
        },
    )
    session.commit()
    return loan


# --- read helpers ------------------------------------------------------------


def list_loans(
    session: Session,
    *,
    status: LoanStatus | None = None,
    member_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Loan], int]:
    stmt = select(Loan).join(Member, Loan.member_id == Member.id)
    if status is not None:
        stmt = stmt.where(Loan.status == status)
    if member_id is not None:
        stmt = stmt.where(Loan.member_id == member_id)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            or_(
                Loan.loan_code.ilike(needle),
                Member.full_name.ilike(needle),
                Member.member_code.ilike(needle),
            )
        )

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    loans = session.scalars(
        stmt.order_by(Loan.applied_on, Loan.loan_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(loans), total or 0


def get(session: Session, loan_id: uuid.UUID) -> Loan:
    return _load(session, loan_id)


def installments_for(session: Session, loan_id: uuid.UUID) -> list[Installment]:
    return list(
        session.scalars(
            select(Installment).where(Installment.loan_id == loan_id).order_by(Installment.seq)
        ).all()
    )
