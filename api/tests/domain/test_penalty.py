"""Late fees — DOMAIN.md §8. Flat, once per overdue installment, never compounds.
Pure: everything is a function of (installment, config, as_of)."""

import datetime as dt
from decimal import Decimal

from app.domain.penalty import InstallmentSnapshot, fee_outstanding, penalty_due

D = Decimal
DUE = dt.date(2026, 1, 26)  # installment 3 of worked example A
GRACE = 3
FEE = D("100.00")


def snap(**overrides) -> InstallmentSnapshot:
    base = dict(
        seq=3,
        due_date=DUE,
        principal_due=D("4166.67"),
        interest_due=D("230.77"),
        amount_due=D("4397.44"),
        principal_paid=D("0.00"),
        interest_paid=D("0.00"),
        fee_paid=D("0.00"),
    )
    base.update(overrides)
    return InstallmentSnapshot(**base)


class TestPenaltyDue:
    def test_no_fee_on_a_paid_installment(self):
        paid = snap(principal_paid=D("4166.67"), interest_paid=D("230.77"))
        assert penalty_due(paid, FEE, GRACE, dt.date(2026, 3, 1)) == D("0.00")

    def test_no_fee_before_due_date(self):
        assert penalty_due(snap(), FEE, GRACE, dt.date(2026, 1, 20)) == D("0.00")

    def test_no_fee_on_the_due_date_itself(self):
        assert penalty_due(snap(), FEE, GRACE, DUE) == D("0.00")

    def test_no_fee_on_last_day_of_grace(self):
        assert penalty_due(snap(), FEE, GRACE, dt.date(2026, 1, 29)) == D("0.00")

    def test_fee_applied_on_first_day_past_grace(self):
        assert penalty_due(snap(), FEE, GRACE, dt.date(2026, 1, 30)) == FEE

    def test_fee_charged_once_and_never_compounds(self):
        three_days = penalty_due(snap(), FEE, GRACE, dt.date(2026, 1, 29) + dt.timedelta(days=1))
        three_hundred_days = penalty_due(snap(), FEE, GRACE, dt.date(2027, 11, 22))
        assert three_days == three_hundred_days == FEE

    def test_zero_late_fee_configuration_produces_no_fee(self):
        assert penalty_due(snap(), D("0.00"), GRACE, dt.date(2026, 6, 1)) == D("0.00")


class TestFeeOutstanding:
    def test_unpaid_fee_is_owed_in_full(self):
        assert fee_outstanding(snap(), FEE, GRACE, dt.date(2026, 2, 1)) == FEE

    def test_partially_paid_fee_ows_only_the_remainder(self):
        assert fee_outstanding(snap(fee_paid=D("40.00")), FEE, GRACE, dt.date(2026, 2, 1)) == D(
            "60.00"
        )

    def test_fully_paid_fee_ows_nothing(self):
        assert fee_outstanding(snap(fee_paid=FEE), FEE, GRACE, dt.date(2026, 2, 1)) == D("0.00")

    def test_fee_paid_before_any_fee_was_due_ows_nothing(self):
        # a fee paid "early" (e.g. charged then grace rules changed) never creates debt
        assert fee_outstanding(snap(fee_paid=D("10.00")), D("0.00"), GRACE, DUE) == D("0.00")
