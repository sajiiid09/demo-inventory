"""Late fees — DOMAIN.md §8.

Flat, charged once per overdue installment after a grace period. Never grows
with time, never compounds. Computed on read (ADR-004): a fee becomes a stored
row only at the moment a repayment allocates money to it.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import ZERO, q2


@dataclass(frozen=True)
class InstallmentSnapshot:
    """Plain values of one installment row — what services pass into the domain.

    The pure layer never touches SQLAlchemy; services translate rows into
    snapshots and results back. This is the ADR-011 boundary.
    """

    seq: int
    due_date: dt.date
    principal_due: Decimal
    interest_due: Decimal
    amount_due: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    fee_paid: Decimal

    @property
    def is_fully_paid(self) -> bool:
        return self.principal_paid + self.interest_paid >= self.amount_due

    @property
    def principal_owed(self) -> Decimal:
        return self.principal_due - self.principal_paid

    @property
    def interest_owed(self) -> Decimal:
        return self.interest_due - self.interest_paid


def penalty_due(
    installment: InstallmentSnapshot,
    late_fee: Decimal,
    grace_days: int,
    as_of: dt.date,
) -> Decimal:
    """The fee owed on this installment as of `as_of` (the full flat fee or zero)."""
    if installment.is_fully_paid:
        return ZERO
    if as_of <= installment.due_date + dt.timedelta(days=grace_days):
        return ZERO
    return q2(late_fee)


def fee_outstanding(
    installment: InstallmentSnapshot,
    late_fee: Decimal,
    grace_days: int,
    as_of: dt.date,
) -> Decimal:
    """Fee still owed: accrued minus whatever earlier payments already covered."""
    accrued = penalty_due(installment, late_fee, grace_days, as_of)
    return max(ZERO, q2(accrued - installment.fee_paid))
