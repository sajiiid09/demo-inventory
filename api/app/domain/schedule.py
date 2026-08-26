"""Schedule generation — DOMAIN.md §5.

Pure: amounts come from money/interest, dates from calendar arithmetic.
The final row absorbs both remainders so SUM(amount_due) == total_payable,
exactly, to the paisa — the invariant everything else relies on.
"""

import calendar
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from app.domain.interest import PERIODS_PER_YEAR, flat_interest
from app.domain.money import q2, split_with_remainder


@dataclass(frozen=True)
class ComputedTerms:
    """The three figures frozen at disbursement (rule R4)."""

    total_interest: Decimal
    total_payable: Decimal
    installment_amount: Decimal


def compute_terms(
    principal: Decimal, annual_rate: Decimal, term_count: int, frequency: str
) -> ComputedTerms:
    interest = flat_interest(principal, annual_rate, term_count, frequency)
    total = q2(principal + interest)
    return ComputedTerms(
        total_interest=interest,
        total_payable=total,
        installment_amount=q2(total / term_count),
    )


def _add_months(start: dt.date, months: int) -> dt.date:
    """Add months, clamping the day to the end of a short month.

    Always computed from the ORIGINAL day-of-month, never carried forward from
    a clamped date: 31 Jan → 28 Feb → 31 Mar (DOMAIN.md §5.2).
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def due_dates(start_date: dt.date, term_count: int, frequency: str) -> list[dt.date]:
    if frequency not in PERIODS_PER_YEAR:
        raise ValueError(f"unknown frequency {frequency!r}")
    if frequency == "WEEKLY":
        step = dt.timedelta(days=7)
        return [start_date + step * n for n in range(1, term_count + 1)]
    return [_add_months(start_date, n) for n in range(1, term_count + 1)]


@dataclass(frozen=True)
class ScheduleRow:
    seq: int
    due_date: dt.date
    principal_due: Decimal
    interest_due: Decimal
    amount_due: Decimal


def build_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    term_count: int,
    frequency: str,
    start_date: dt.date,
) -> list[ScheduleRow]:
    terms = compute_terms(principal, annual_rate, term_count, frequency)
    principal_parts = split_with_remainder(principal, term_count)
    interest_parts = split_with_remainder(terms.total_interest, term_count)
    dates = due_dates(start_date, term_count, frequency)

    return [
        ScheduleRow(
            seq=seq,
            due_date=dates[seq - 1],
            principal_due=principal_parts[seq - 1],
            interest_due=interest_parts[seq - 1],
            amount_due=q2(principal_parts[seq - 1] + interest_parts[seq - 1]),
        )
        for seq in range(1, term_count + 1)
    ]
