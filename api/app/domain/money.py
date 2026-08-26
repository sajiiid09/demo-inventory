"""Money primitives — the only place rounding is defined (ADR-008).

Everything downstream (interest, schedules, allocations) calls q2(); no other
module quantizes on its own.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def q2(value: Decimal) -> Decimal:
    """Round to exactly 2 decimal places, HALF_UP (0.005 → 0.01).

    Python's default is banker's rounding; money must never use it.
    """
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def split_with_remainder(total: Decimal, n: int) -> list[Decimal]:
    """Split `total` into n parts of 2dp each that sum to `total` exactly.

    The first n−1 parts are the rounded quotient; the last part absorbs the
    difference. Only the last element may differ (DOMAIN.md §5.1).
    """
    if n < 1:
        raise ValueError("n must be a positive number of parts")
    base = q2(total / n)
    parts = [base] * (n - 1)
    parts.append(q2(total - base * (n - 1)))
    return parts
