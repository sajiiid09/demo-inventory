"""Small query helpers shared by services."""

import uuid
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.models import Installment

ZERO = Decimal("0.00")


def next_code(session: Session, column, prefix: str) -> str:
    """Next sequential code: M-000001, L-000001, R-000001 … never reused.

    Reads MAX(numeric suffix) inside the caller's transaction; the UNIQUE
    constraint on the column is the backstop if two transactions race.
    """
    last = session.scalar(
        select(func.max(func.substring(column, len(prefix) + 1).cast(Integer)))
    )
    return f"{prefix}{(last or 0) + 1:06d}"


def outstanding_by_loan(session: Session, loan_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Outstanding = SUM(amount_due − principal_paid − interest_paid) per loan.

    Principal and interest only — accrued late fees are excluded by definition
    (DOMAIN.md §1). Loans without installments owe nothing yet.
    """
    if not loan_ids:
        return {}
    rows = session.execute(
        select(
            Installment.loan_id,
            func.sum(Installment.amount_due - Installment.principal_paid - Installment.interest_paid),
        )
        .where(Installment.loan_id.in_(loan_ids))
        .group_by(Installment.loan_id)
    ).all()
    return {loan_id: (total or ZERO) for loan_id, total in rows}
