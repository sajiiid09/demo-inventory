"""Repayment allocation — DOMAIN.md §9. Oldest installment first; within one
installment: accrued fee → interest → principal; leftovers cascade and are reported."""

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.allocation import allocate
from app.domain.penalty import InstallmentSnapshot

D = Decimal
START = dt.date(2026, 1, 5)
GRACE = 3
FEE = D("100.00")


def snapshot(seq: int, **overrides) -> InstallmentSnapshot:
    """Rows 1..24 of worked example A: 4,166.67 principal + 230.77 interest each."""
    base = dict(
        seq=seq,
        due_date=START + dt.timedelta(days=7 * seq),
        principal_due=D("4166.67"),
        interest_due=D("230.77"),
        amount_due=D("4397.44"),
        principal_paid=D("0.00"),
        interest_paid=D("0.00"),
        fee_paid=D("0.00"),
    )
    if seq == 24:  # last row absorbs the remainders
        base.update(
            principal_due=D("4166.59"),
            interest_due=D("230.75"),
            amount_due=D("4397.34"),
        )
    base.update(overrides)
    return InstallmentSnapshot(**base)


def fresh_loan(n: int = 24) -> list[InstallmentSnapshot]:
    return [snapshot(i) for i in range(1, n + 1)]


class TestAllocation:
    def test_exact_installment_payment_settles_one_row(self):
        plan = allocate(D("4397.44"), fresh_loan(3), D("0.00"), GRACE, START)
        assert len(plan.allocations) == 1
        a = plan.allocations[0]
        assert (a.seq, a.interest, a.principal) == (1, D("230.77"), D("4166.67"))
        assert plan.leftover == D("0.00")

    def test_partial_payment_applies_to_oldest_installment(self):
        plan = allocate(D("500.00"), fresh_loan(3), D("0.00"), GRACE, START)
        assert len(plan.allocations) == 1
        a = plan.allocations[0]
        assert a.seq == 1
        assert a.interest == D("230.77")   # interest before principal
        assert a.principal == D("269.23")  # 500.00 − 230.77

    def test_large_payment_cascades_across_installments(self):
        # The 10,000.00 case from DOMAIN.md §9 — three allocation lines
        plan = allocate(D("10000.00"), fresh_loan(24), D("0.00"), GRACE, START)
        assert plan.leftover == D("0.00")
        assert [(a.seq, a.fee, a.interest, a.principal) for a in plan.allocations] == [
            (1, D("0.00"), D("230.77"), D("4166.67")),
            (2, D("0.00"), D("230.77"), D("4166.67")),
            (3, D("0.00"), D("230.77"), D("974.35")),
        ]

    def test_allocation_order_is_fee_then_interest_then_principal(self):
        as_of = START + dt.timedelta(days=30)  # well past row 1's grace
        plan = allocate(D("500.00"), fresh_loan(3), FEE, GRACE, as_of)
        a = plan.allocations[0]
        assert a.seq == 1
        assert a.fee == FEE
        assert a.interest == D("230.77")
        assert a.principal == D("169.23")  # 500 − 100 − 230.77

    def test_fee_is_consumed_before_interest_on_overdue_row(self):
        as_of = START + dt.timedelta(days=40)
        # a payment big enough to cover fee + interest but not all principal
        plan = allocate(D("400.00"), fresh_loan(3), FEE, GRACE, as_of)
        a = plan.allocations[0]
        assert a.fee == D("100.00")
        assert a.interest == D("230.77")
        assert a.principal == D("69.23")

    @pytest.mark.parametrize(
        "amount,n,fee",
        [
            ("10000.00", 24, "0.00"),
            ("4397.44", 24, "0.00"),
            ("1.00", 24, "0.00"),
            ("500.00", 3, "100.00"),
            ("105538.46", 24, "0.00"),   # settle example A in one payment
            ("13200.00", 3, "100.00"),   # settle 3 rows + fees
            ("79153.82", 24, "100.00"),  # settlement-quote case, §10 (6 rows pre-paid)
        ],
    )
    def test_allocations_sum_to_payment_amount(self, amount, n, fee):
        rows = fresh_loan(n)
        plan = allocate(D(amount), rows, D(fee), GRACE, START + dt.timedelta(days=90))
        applied = sum((a.fee + a.interest + a.principal for a in plan.allocations), D("0.00"))
        assert applied + plan.leftover == D(amount)

    @pytest.mark.parametrize(
        "amount,n",
        [("4397.44", 24), ("10000.00", 24), ("105538.46", 24), ("300.00", 1), ("5237.34", 2)],
    )
    def test_payment_never_over_allocates_an_installment(self, amount, n):
        rows = fresh_loan(n)
        plan = allocate(D(amount), rows, D("0.00"), GRACE, START)
        due = {r.seq: r for r in rows}
        for a in plan.allocations:
            r = due[a.seq]
            assert a.principal <= r.principal_due
            assert a.interest <= r.interest_due
            assert a.fee <= D("0.00") + FEE  # fee config was zero here

    def test_full_settlement_covers_every_remaining_row(self):
        # rows 1–2 already paid; a settlement-sized payment clears rows 3–24 exactly
        rows = fresh_loan(24)
        for i in (0, 1):
            rows[i] = snapshot(
                rows[i].seq,
                principal_paid=rows[i].principal_due,
                interest_paid=rows[i].interest_due,
            )
        outstanding = sum(
            (r.amount_due - r.principal_paid - r.interest_paid for r in rows), D("0.00")
        )
        plan = allocate(outstanding, rows, D("0.00"), GRACE, START)
        assert plan.leftover == D("0.00")
        assert len(plan.allocations) == 22
        assert {a.seq for a in plan.allocations} == set(range(3, 25))

    def test_leftover_money_is_reported_not_silently_kept(self):
        rows = fresh_loan(2)
        total = sum((r.amount_due for r in rows), D("0.00"))
        plan = allocate(total + D("0.01"), rows, D("0.00"), GRACE, START)
        assert plan.leftover == D("0.01")

    def test_paid_installments_are_skipped(self):
        rows = fresh_loan(3)
        rows[0] = snapshot(1, principal_paid=D("4166.67"), interest_paid=D("230.77"))
        plan = allocate(D("4397.44"), rows, D("0.00"), GRACE, START)
        assert [a.seq for a in plan.allocations] == [2]

    def test_allocation_total_property_sums_the_three_ways(self):
        plan = allocate(D("10000.00"), fresh_loan(24), D("0.00"), GRACE, START)
        assert [a.total for a in plan.allocations] == [
            D("4397.44"), D("4397.44"), D("1205.12"),
        ]
