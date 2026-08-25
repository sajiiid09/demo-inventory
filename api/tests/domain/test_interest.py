"""Flat interest — DOMAIN.md §4. interest = principal × rate × (term / periods)."""

from decimal import Decimal

import pytest

from app.domain.interest import flat_interest


class TestFlatInterest:
    def test_weekly_flat_interest_matches_worked_example(self):
        # DOMAIN.md §6: 100,000.00 · 12% · 24 wk → 5,538.46
        assert flat_interest(Decimal("100000.00"), Decimal("12.00"), 24, "WEEKLY") == Decimal(
            "5538.46"
        )

    def test_monthly_flat_interest_matches_worked_example(self):
        # DOMAIN.md §7: 100,000.00 · 12% · 12 mo → 12,000.00
        assert flat_interest(Decimal("100000.00"), Decimal("12.00"), 12, "MONTHLY") == Decimal(
            "12000.00"
        )

    def test_zero_rate_produces_zero_interest(self):
        assert flat_interest(Decimal("100000.00"), Decimal("0.00"), 24, "WEEKLY") == Decimal(
            "0.00"
        )

    def test_interest_scales_linearly_with_term(self):
        # flat interest is linear: 26 weeks is exactly twice 13 weeks
        thirteen = flat_interest(Decimal("100000.00"), Decimal("12.00"), 13, "WEEKLY")
        twenty_six = flat_interest(Decimal("100000.00"), Decimal("12.00"), 26, "WEEKLY")
        assert thirteen == Decimal("3000.00")
        assert twenty_six == Decimal("6000.00")

    def test_unknown_frequency_is_rejected(self):
        with pytest.raises(ValueError):
            flat_interest(Decimal("100000.00"), Decimal("12.00"), 24, "DAILY")
