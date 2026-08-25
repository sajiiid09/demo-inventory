"""Schedule generation — DOMAIN.md §5–7. The most important invariant lives here:
SUM(amount_due) == total_payable, exactly, for every loan shape."""

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.schedule import build_schedule, compute_terms, due_dates

D = Decimal

# The canonical weekly example (DOMAIN.md §6), every documented row.
WEEKLY = dict(principal=D("100000.00"), rate=D("12.00"), term=24, frequency="WEEKLY")
MONTHLY = dict(principal=D("100000.00"), rate=D("12.00"), term=12, frequency="MONTHLY")


class TestWorkedExamples:
    def test_weekly_example_matches_documented_table(self):
        rows = build_schedule(
            principal=WEEKLY["principal"],
            annual_rate=WEEKLY["rate"],
            term_count=WEEKLY["term"],
            frequency=WEEKLY["frequency"],
            start_date=dt.date(2026, 1, 5),
        )
        assert len(rows) == 24

        def row(seq, due, p, i, a):
            return (seq, due, D(p), D(i), D(a))

        expected = [
            row(1, dt.date(2026, 1, 12), "4166.67", "230.77", "4397.44"),
            row(2, dt.date(2026, 1, 19), "4166.67", "230.77", "4397.44"),
            row(3, dt.date(2026, 1, 26), "4166.67", "230.77", "4397.44"),
            # rows 4–22 follow the same pattern as rows 1–3
            row(23, dt.date(2026, 6, 15), "4166.67", "230.77", "4397.44"),
            row(24, dt.date(2026, 6, 22), "4166.59", "230.75", "4397.34"),
        ]
        for seq, due, p, i, a in expected:
            r = rows[seq - 1]
            assert (r.seq, r.due_date, r.principal_due, r.interest_due, r.amount_due) == (
                seq, due, p, i, a,
            )
        for r in rows[3:22]:  # rows 4–22
            assert r.principal_due == D("4166.67")
            assert r.interest_due == D("230.77")
            assert r.amount_due == D("4397.44")

    def test_monthly_example_matches_documented_table(self):
        rows = build_schedule(
            principal=MONTHLY["principal"],
            annual_rate=MONTHLY["rate"],
            term_count=MONTHLY["term"],
            frequency=MONTHLY["frequency"],
            start_date=dt.date(2026, 1, 5),
        )
        assert len(rows) == 12
        first, last = rows[0], rows[-1]
        assert first.due_date == dt.date(2026, 2, 5)
        assert first.principal_due == D("8333.33")
        assert first.interest_due == D("1000.00")
        assert first.amount_due == D("9333.33")
        assert last.due_date == dt.date(2027, 1, 5)
        assert last.principal_due == D("8333.37")
        assert last.interest_due == D("1000.00")
        assert last.amount_due == D("9333.37")
        for r in rows[:-1]:
            assert r.amount_due == D("9333.33")

    def test_weekly_totals_match_document(self):
        terms = compute_terms(
            WEEKLY["principal"], WEEKLY["rate"], WEEKLY["term"], WEEKLY["frequency"]
        )
        assert terms.total_interest == D("5538.46")
        assert terms.total_payable == D("105538.46")
        assert terms.installment_amount == D("4397.44")

    def test_monthly_totals_match_document(self):
        terms = compute_terms(
            MONTHLY["principal"], MONTHLY["rate"], MONTHLY["term"], MONTHLY["frequency"]
        )
        assert terms.total_interest == D("12000.00")
        assert terms.total_payable == D("112000.00")
        assert terms.installment_amount == D("9333.33")


# Awkward principals, awkward terms, rates that produce long decimals.
SHAPES = [
    (D("100000.00"), D("12.00"), 24, "WEEKLY"),
    (D("100000.00"), D("12.00"), 12, "MONTHLY"),
    (D("10000.03"), D("12.00"), 7, "WEEKLY"),
    (D("10000.03"), D("12.00"), 13, "WEEKLY"),
    (D("10000.03"), D("8.75"), 53, "WEEKLY"),
    (D("33333.33"), D("3.30"), 7, "MONTHLY"),
    (D("33333.33"), D("3.30"), 13, "MONTHLY"),
    (D("99999.99"), D("12.50"), 9, "WEEKLY"),
    (D("99999.99"), D("12.50"), 9, "MONTHLY"),
    (D("1.01"), D("25.00"), 2, "WEEKLY"),
    (D("1.01"), D("25.00"), 3, "MONTHLY"),
    (D("0.01"), D("99.99"), 1, "WEEKLY"),
    (D("123456.78"), D("18.18"), 6, "MONTHLY"),
    (D("123456.78"), D("18.18"), 17, "WEEKLY"),
    (D("50000.00"), D("0.00"), 10, "WEEKLY"),   # zero rate
    (D("50000.00"), D("0.00"), 10, "MONTHLY"),
    (D("77777.77"), D("7.77"), 52, "WEEKLY"),   # a full year of weeks
    (D("77777.77"), D("7.77"), 24, "MONTHLY"),  # two years of months
    (D("2000.00"), D("15.00"), 4, "WEEKLY"),
    (D("2000.00"), D("15.00"), 5, "MONTHLY"),
    (D("30000.00"), D("10.00"), 1, "WEEKLY"),   # n = 1
    (D("30000.00"), D("10.00"), 1, "MONTHLY"),
    (D("49999.99"), D("9.99"), 11, "WEEKLY"),
    (D("49999.99"), D("9.99"), 11, "MONTHLY"),
    (D("60000.00"), D("13.13"), 19, "WEEKLY"),
    (D("60000.00"), D("13.13"), 19, "MONTHLY"),
    (D("8000.08"), D("22.22"), 8, "WEEKLY"),
    (D("8000.08"), D("22.22"), 8, "MONTHLY"),
    (D("15000.00"), D("6.50"), 26, "WEEKLY"),
    (D("15000.00"), D("6.50"), 18, "MONTHLY"),
]


class TestScheduleInvariants:
    @pytest.mark.parametrize("principal,rate,term,frequency", SHAPES)
    def test_schedule_sums_exactly_to_total_payable(self, principal, rate, term, frequency):
        rows = build_schedule(principal, rate, term, frequency, dt.date(2026, 1, 5))
        terms = compute_terms(principal, rate, term, frequency)
        assert sum((r.amount_due for r in rows), D("0.00")) == terms.total_payable

    @pytest.mark.parametrize("principal,rate,term,frequency", SHAPES)
    def test_principal_rows_sum_to_principal(self, principal, rate, term, frequency):
        rows = build_schedule(principal, rate, term, frequency, dt.date(2026, 1, 5))
        assert sum((r.principal_due for r in rows), D("0.00")) == principal

    @pytest.mark.parametrize("principal,rate,term,frequency", SHAPES)
    def test_interest_rows_sum_to_total_interest(self, principal, rate, term, frequency):
        rows = build_schedule(principal, rate, term, frequency, dt.date(2026, 1, 5))
        terms = compute_terms(principal, rate, term, frequency)
        assert sum((r.interest_due for r in rows), D("0.00")) == terms.total_interest

    @pytest.mark.parametrize("principal,rate,term,frequency", SHAPES)
    def test_last_installment_absorbs_both_remainders(self, principal, rate, term, frequency):
        rows = build_schedule(principal, rate, term, frequency, dt.date(2026, 1, 5))
        if term == 1:
            return  # single row *is* the remainder
        body, last = rows[:-1], rows[-1]
        assert all(r.principal_due == body[0].principal_due for r in body)
        assert all(r.interest_due == body[0].interest_due for r in body)
        assert last.principal_due == principal - body[0].principal_due * (term - 1)
        assert last.interest_due == compute_terms(
            principal, rate, term, frequency
        ).total_interest - body[0].interest_due * (term - 1)


class TestDueDates:
    def test_weekly_due_dates_step_by_seven_days(self):
        dates = due_dates(dt.date(2026, 1, 5), 10, "WEEKLY")
        assert dates[0] == dt.date(2026, 1, 12)
        assert dates[-1] == dt.date(2026, 3, 16)
        assert all((b - a).days == 7 for a, b in zip(dates, dates[1:]))

    def test_monthly_due_dates_step_by_one_month(self):
        dates = due_dates(dt.date(2026, 1, 5), 12, "MONTHLY")
        assert dates[0] == dt.date(2026, 2, 5)
        assert dates[1] == dt.date(2026, 3, 5)
        assert dates[-1] == dt.date(2027, 1, 5)

    def test_monthly_due_date_clamps_to_month_end(self):
        # 31 Jan → 28 Feb → 31 Mar (clamped from the ORIGINAL day each time)
        dates = due_dates(dt.date(2026, 1, 31), 3, "MONTHLY")
        assert dates == [dt.date(2026, 2, 28), dt.date(2026, 3, 31), dt.date(2026, 4, 30)]

    def test_monthly_due_date_clamps_in_leap_year(self):
        dates = due_dates(dt.date(2028, 1, 31), 2, "MONTHLY")
        assert dates == [dt.date(2028, 2, 29), dt.date(2028, 3, 31)]

    def test_single_installment_loan_is_valid(self):
        rows = build_schedule(D("30000.00"), D("10.00"), 1, "WEEKLY", dt.date(2026, 1, 5))
        assert len(rows) == 1
        assert rows[0].seq == 1
        assert rows[0].amount_due == D("30000.00") + D("57.69")  # 30000×0.10×(1/52)
