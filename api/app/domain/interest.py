"""Flat interest — DOMAIN.md §4.

    interest = principal × annual_rate × (term_count / periods_per_year)

`term_count` is the number of installments, not years. Flat means computed once
on the original principal and never recalculated as the balance falls.
"""

from decimal import Decimal

from app.domain.money import ZERO, q2

PERIODS_PER_YEAR: dict[str, int] = {
    "WEEKLY": 52,
    "MONTHLY": 12,
}


def flat_interest(
    principal: Decimal, annual_rate: Decimal, term_count: int, frequency: str
) -> Decimal:
    periods = PERIODS_PER_YEAR.get(frequency)
    if periods is None:
        raise ValueError(f"unknown frequency {frequency!r}; expected one of {list(PERIODS_PER_YEAR)}")
    rate = annual_rate / Decimal("100")
    raw = principal * rate * (Decimal(term_count) / Decimal(periods))
    return q2(raw) if raw != 0 else ZERO
