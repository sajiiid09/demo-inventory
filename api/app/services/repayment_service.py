"""Recording repayments — DOMAIN.md §9, in the documented order:

1. load the loan FOR UPDATE
2. guard R3 (status) and R5 (dates)
3. compute fees and the allocation plan — PURE, no writes yet
4. guard R6 (leftover money is reported, never silently kept)
5. write: repayments, repayment_allocations, installment increments,
   a REPAYMENT ledger entry, an audit row
6. auto-close the loan if every installment is now settled

Every decision happens before the first write; the writes apply a plan that
has already been validated.
"""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit, clock
from app.domain.allocation import AllocationPlan, allocate
from app.domain.money import q2
from app.domain.penalty import InstallmentSnapshot, fee_outstanding
from app.errors import ApiError, invalid_date, invalid_state, not_found
from app.models import (
    Installment,
    LedgerDirection,
    LedgerEntry,
    LedgerEntryType,
    Loan,
    LoanStatus,
    PaymentMethod,
    Repayment,
    RepaymentAllocation,
    User,
)
from app.services.helpers import next_code
from app.services.loan_service import installments_for

ZERO = Decimal("0.00")


def record(
    session: Session,
    *,
    loan_id: uuid.UUID,
    amount: Decimal,
    paid_on: dt.date,
    method: PaymentMethod,
    note: str | None,
    actor: User,
) -> tuple[Repayment, AllocationPlan, Loan]:
    # 1 — lock the loan row: concurrent payments serialise here.
    loan = session.scalar(
        select(Loan).where(Loan.id == loan_id).with_for_update(of=Loan)
    )
    if loan is None:
        raise not_found("No loan with this id.")

    # 2 — R3: only DISBURSED loans accept repayments (CLOSED is terminal).
    if loan.status != LoanStatus.DISBURSED:
        raise invalid_state(
            f"Loan {loan.loan_code} is {loan.status.value}; "
            f"only DISBURSED loans accept repayments."
        )
    # R5: not before the money left, not in the future.
    if paid_on < (loan.disbursed_on or dt.date.min):
        raise invalid_date(
            f"paid_on ({paid_on}) precedes disbursed_on ({loan.disbursed_on}) (R5)."
        )
    if paid_on > clock.today():
        raise invalid_date(f"paid_on ({paid_on}) is in the future (R5).")

    # 3 — the pure plan. Snapshots ordered oldest first: due_date, then seq.
    installments = installments_for(session, loan.id)
    snapshots = [_snapshot(i) for i in installments]
    plan = allocate(amount, snapshots, loan.late_fee, loan.grace_days, paid_on)

    # 4 — R6: leftover money means the payment exceeds outstanding + fees.
    if plan.leftover > ZERO:
        settlement = q2(amount - plan.leftover)
        raise ApiError(
            422,
            "AMOUNT_EXCEEDS_OUTSTANDING",
            f"Payment of {amount} exceeds the total outstanding plus accrued fees. "
            f"The exact settlement figure as of {paid_on} is {settlement} (R6).",
        )

    # 5 — apply the plan. Writes only from here on.
    repayment = Repayment(
        receipt_no=next_code(session, Repayment.receipt_no, "R-"),
        loan_id=loan.id,
        amount=amount,
        paid_on=paid_on,
        method=method,
        note=note,
        received_by=actor.id,
    )
    session.add(repayment)
    session.flush()  # repayment.id before the allocations reference it

    by_seq = {i.seq: i for i in installments}
    for line in plan.allocations:
        inst = by_seq[line.seq]
        session.add(
            RepaymentAllocation(
                repayment_id=repayment.id,
                installment_id=inst.id,
                fee_amount=line.fee,
                interest_amount=line.interest,
                principal_amount=line.principal,
            )
        )
        inst.principal_paid += line.principal
        inst.interest_paid += line.interest
        inst.fee_paid += line.fee

    session.add(
        LedgerEntry(
            entry_type=LedgerEntryType.REPAYMENT,
            direction=LedgerDirection.IN,
            loan_id=loan.id,
            amount=amount,
            occurred_on=paid_on,
            source_id=repayment.id,
            created_by=actor.id,
        )
    )
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.REPAYMENT_RECORDED,
        entity_type="repayment",
        entity_id=repayment.id,
        after={
            "receipt_no": repayment.receipt_no,
            "loan_code": loan.loan_code,
            "amount": str(amount),
            "paid_on": str(paid_on),
            "allocation_lines": len(plan.allocations),
        },
    )

    # 6 — automatic closure, never triggered by a human.
    if all(_is_fully_paid(i) for i in installments):
        loan.status = LoanStatus.CLOSED
        loan.closed_at = func.now()
        audit.record(
            session,
            actor_id=actor.id,
            action=audit.LOAN_CLOSED,
            entity_type="loan",
            entity_id=loan.id,
            before={"status": "DISBURSED"},
            after={"status": "CLOSED", "receipt_no": repayment.receipt_no},
        )

    session.commit()
    return repayment, plan, loan


def settlement_quote(
    session: Session, *, loan_id: uuid.UUID, as_of: dt.date
) -> tuple[Decimal, Decimal, Decimal, Loan]:
    """(outstanding, accrued_fees, settlement_total, loan) as of `as_of`.

    Flat interest means no rebate: settling early costs the remaining
    amount_due plus any accrued fees (DOMAIN.md §10).
    """
    loan = session.get(Loan, loan_id)
    if loan is None:
        raise not_found("No loan with this id.")
    if loan.status not in (LoanStatus.DISBURSED, LoanStatus.CLOSED):
        raise invalid_state(
            f"Loan {loan.loan_code} is {loan.status.value}; "
            f"only DISBURSED or CLOSED loans have a settlement figure."
        )

    installments = installments_for(session, loan.id)
    outstanding = ZERO
    fees = ZERO
    for inst in installments:
        outstanding += inst.amount_due - inst.principal_paid - inst.interest_paid
        fees += fee_outstanding(
            _snapshot(inst), loan.late_fee, loan.grace_days, as_of
        )
    return outstanding, fees, q2(outstanding + fees), loan


def list_repayments(
    session: Session,
    *,
    receipt_no: str | None = None,
    loan_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    method: PaymentMethod | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Repayment], int]:
    stmt = select(Repayment).join(Loan, Repayment.loan_id == Loan.id)
    if receipt_no:
        stmt = stmt.where(Repayment.receipt_no.ilike(f"%{receipt_no}%"))
    if loan_id is not None:
        stmt = stmt.where(Repayment.loan_id == loan_id)
    if member_id is not None:
        stmt = stmt.where(Loan.member_id == member_id)
    if date_from is not None:
        stmt = stmt.where(Repayment.paid_on >= date_from)
    if date_to is not None:
        stmt = stmt.where(Repayment.paid_on <= date_to)
    if method is not None:
        stmt = stmt.where(Repayment.method == method)

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    repayments = session.scalars(
        stmt.order_by(Repayment.paid_on.desc(), Repayment.receipt_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(repayments), total or 0


def get(session: Session, repayment_id: uuid.UUID) -> Repayment:
    repayment = session.get(Repayment, repayment_id)
    if repayment is None:
        raise not_found("No repayment with this id.")
    return repayment


def allocation_lines(session: Session, repayment_id: uuid.UUID) -> list[tuple]:
    """[(seq, due_date, fee, interest, principal)] ordered by installment seq."""
    return list(
        session.execute(
            select(
                Installment.seq,
                Installment.due_date,
                RepaymentAllocation.fee_amount,
                RepaymentAllocation.interest_amount,
                RepaymentAllocation.principal_amount,
            )
            .join(Installment, RepaymentAllocation.installment_id == Installment.id)
            .where(RepaymentAllocation.repayment_id == repayment_id)
            .order_by(Installment.seq)
        ).all()
    )


def _snapshot(inst: Installment) -> InstallmentSnapshot:
    return InstallmentSnapshot(
        seq=inst.seq,
        due_date=inst.due_date,
        principal_due=inst.principal_due,
        interest_due=inst.interest_due,
        amount_due=inst.amount_due,
        principal_paid=inst.principal_paid,
        interest_paid=inst.interest_paid,
        fee_paid=inst.fee_paid,
    )


def _is_fully_paid(inst: Installment) -> bool:
    return inst.principal_paid + inst.interest_paid >= inst.amount_due
