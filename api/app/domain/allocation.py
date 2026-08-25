"""Repayment allocation — DOMAIN.md §9.

A payment is allocated to specific installments, oldest first. Within one
installment money is consumed in a fixed order: accrued fee → interest →
principal. Whatever remains cascades to the next installment. If money is left
over after every installment is satisfied, it is REPORTED as `leftover` — the
service turns that into rule R6's AMOUNT_EXCEEDS_OUTSTANDING with the exact
settlement figure.

Pure: same inputs, same plan, forever. No writes happen here.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.money import ZERO, q2
from app.domain.penalty import InstallmentSnapshot, fee_outstanding


@dataclass(frozen=True)
class Allocation:
    """How much of the payment went to one installment, split three ways."""

    seq: int
    fee: Decimal
    interest: Decimal
    principal: Decimal

    @property
    def total(self) -> Decimal:
        return q2(self.fee + self.interest + self.principal)


@dataclass(frozen=True)
class AllocationPlan:
    allocations: list[Allocation] = field(default_factory=list)
    leftover: Decimal = ZERO


def allocate(
    amount: Decimal,
    installments: list[InstallmentSnapshot],
    late_fee: Decimal,
    grace_days: int,
    as_of: dt.date,
) -> AllocationPlan:
    """Plan the allocation of `amount` across `installments` (oldest first).

    Callers must pass installments ordered by (due_date, seq). Fully paid rows
    are skipped. No installment is ever over-allocated.
    """
    remaining = q2(amount)
    lines: list[Allocation] = []

    for row in installments:
        if remaining <= ZERO:
            break
        if row.is_fully_paid:
            continue

        fee_take = min(remaining, fee_outstanding(row, late_fee, grace_days, as_of))
        remaining = q2(remaining - fee_take)

        interest_take = min(remaining, row.interest_owed)
        remaining = q2(remaining - interest_take)

        principal_take = min(remaining, row.principal_owed)
        remaining = q2(remaining - principal_take)

        if fee_take + interest_take + principal_take > ZERO:
            lines.append(
                Allocation(
                    seq=row.seq,
                    fee=q2(fee_take),
                    interest=q2(interest_take),
                    principal=q2(principal_take),
                )
            )

    return AllocationPlan(allocations=lines, leftover=remaining)
