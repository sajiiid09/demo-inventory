"""q2 and split_with_remainder — the foundation of every money figure."""

from decimal import Decimal

import pytest

from app.domain.money import q2, split_with_remainder


class TestQ2:
    def test_rounds_half_up_to_two_decimals(self):
        # 0.005 → 0.01, not banker's rounding (which would give 0.00)
        assert q2(Decimal("0.005")) == Decimal("0.01")
        assert q2(Decimal("2.345")) == Decimal("2.35")
        assert q2(Decimal("2.344")) == Decimal("2.34")

    def test_rounds_negative_values_consistently(self):
        # ROUND_HALF_UP rounds away from zero on ties, both directions
        assert q2(Decimal("-0.005")) == Decimal("-0.01")
        assert q2(Decimal("-2.345")) == Decimal("-2.35")

    def test_already_two_decimals_is_unchanged(self):
        assert q2(Decimal("105538.46")) == Decimal("105538.46")


class TestSplitWithRemainder:
    @pytest.mark.parametrize(
        "total,n",
        [
            (Decimal("100000.00"), 24),
            (Decimal("5538.46"), 24),
            (Decimal("10000.03"), 3),
            (Decimal("10000.03"), 7),
            (Decimal("0.03"), 7),
            (Decimal("1.00"), 3),
            (Decimal("99999.99"), 13),
            (Decimal("333.33"), 53),
            (Decimal("12.00"), 12),
            (Decimal("7.00"), 2),
        ],
    )
    def test_split_with_remainder_sums_exactly(self, total, n):
        parts = split_with_remainder(total, n)
        assert len(parts) == n
        assert sum(parts, Decimal("0.00")) == total
        assert all(p == q2(p) for p in parts)  # every part is exactly 2dp

    def test_split_with_remainder_puts_difference_last(self):
        parts = split_with_remainder(Decimal("100.00"), 3)
        assert parts[0] == parts[1] == Decimal("33.33")
        assert parts[2] == Decimal("33.34")  # only the last element differs

    def test_split_of_zero_returns_zeros(self):
        assert split_with_remainder(Decimal("0.00"), 5) == [Decimal("0.00")] * 5

    def test_split_rejects_non_positive_n(self):
        with pytest.raises(ValueError):
            split_with_remainder(Decimal("10.00"), 0)
