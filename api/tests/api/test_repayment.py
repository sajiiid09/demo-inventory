"""Repayment rules R3/R5/R6, the DOMAIN.md §9 case, receipts, auto-close,
and the append-only triggers — TESTING.md §3."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests.conftest import make_loan


def _pay(clients, loan_id, amount, on, method="CASH", note=None):
    return clients.cashier.post(
        "/repayments",
        json={"loan_id": loan_id, "amount": amount, "paid_on": on, "method": method, "note": note},
    )


class TestGuards:
    def test_repayment_on_undisbursed_loan_is_rejected(self, clients):
        from tests.conftest import make_member

        member = make_member(clients)
        loan = clients.officer.post(
            "/loans",
            json={
                "member_id": member["id"],
                "principal": "10000.00",
                "interest_rate_annual": "12.00",
                "term_count": 4,
                "frequency": "WEEKLY",
                "applied_on": "2026-01-02",
            },
        ).json()
        response = _pay(clients, loan["id"], "100.00", "2026-01-06")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVALID_STATE"

    def test_repayment_before_disbursement_date_is_rejected(self, clients):
        loan = make_loan(clients)  # disbursed 2026-01-05
        response = _pay(clients, loan["id"], "100.00", "2026-01-04")
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_DATE"

    def test_repayment_with_future_date_is_rejected(self, clients, monkeypatch):
        from app import clock

        monkeypatch.setattr(clock, "today", lambda: dt.date(2026, 1, 20))
        loan = make_loan(clients)
        response = _pay(clients, loan["id"], "100.00", "2026-01-21")
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_DATE"


class TestR6:
    def test_repayment_exceeding_outstanding_is_rejected_with_the_figure(self, clients):
        loan = make_loan(clients)  # outstanding 105,538.46, nothing overdue yet
        response = _pay(clients, loan["id"], "105538.47", "2026-01-10")
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "AMOUNT_EXCEEDS_OUTSTANDING"
        assert "105538.46" in detail["message"]


class TestAllocationCase:
    def test_partial_repayment_matches_domain_doc_section_9(self, clients):
        # The canonical case: 10,000.00 against example A, nothing overdue.
        loan = make_loan(clients)
        response = _pay(clients, loan["id"], "10000.00", "2026-01-13")
        assert response.status_code == 201, response.text
        receipt = response.json()
        assert receipt["receipt_no"].startswith("R-")
        assert receipt["loan_status_after"] == "DISBURSED"
        assert receipt["outstanding_after"] == "95538.46"
        assert [
            (a["seq"], a["fee"], a["interest"], a["principal"]) for a in receipt["allocations"]
        ] == [
            (1, "0.00", "230.77", "4166.67"),
            (2, "0.00", "230.77", "4166.67"),
            (3, "0.00", "230.77", "974.35"),
        ]
        # the receipt sums exactly to the payment amount
        assert sum(
            Decimal(a["fee"]) + Decimal(a["interest"]) + Decimal(a["principal"])
            for a in receipt["allocations"]
        ) == Decimal("10000.00")

    def test_overdue_repayment_pays_the_fee_first(self, clients):
        loan = make_loan(clients)  # row 1 due 2026-01-12, grace 3
        # 2026-02-01: row 1 (and row 2, due 01-19) are past grace → 100.00 each
        response = _pay(clients, loan["id"], "500.00", "2026-02-01")
        first = response.json()["allocations"][0]
        assert first["seq"] == 1
        assert first["fee"] == "100.00"
        assert first["interest"] == "230.77"
        assert first["principal"] == "169.23"  # 500 − 100 − 230.77

    def test_settlement_quote_matches_a_settling_payment(self, clients):
        loan = make_loan(clients)
        quote = clients.officer.get(
            f"/loans/{loan['id']}/settlement-quote?as_of=2026-02-15"
        ).json()
        # rows 1–5 are past grace as of 2026-02-15 (due 01-12…02-09, +3 days)
        assert quote["outstanding"] == "105538.46"
        assert quote["accrued_fees"] == "500.00"
        assert quote["settlement_total"] == "106038.46"

        response = _pay(clients, loan["id"], quote["settlement_total"], "2026-02-15")
        receipt = response.json()
        assert receipt["loan_status_after"] == "CLOSED"
        assert receipt["outstanding_after"] == "0.00"

    def test_closed_loan_rejects_further_repayments(self, clients):
        loan = make_loan(clients)
        clients.cashier.post(
            "/repayments",
            json={
                "loan_id": loan["id"],
                "amount": "105538.46",
                "paid_on": "2026-01-10",
                "method": "BANK",
            },
        )
        response = _pay(clients, loan["id"], "10.00", "2026-01-11")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVALID_STATE"


class TestAppendOnly:
    @pytest.fixture()
    def paid_loan(self, clients):
        loan = make_loan(clients)
        response = _pay(clients, loan["id"], "10000.00", "2026-01-13")
        assert response.status_code == 201
        return loan

    def test_repayment_cannot_be_updated(self, paid_loan, db):
        with pytest.raises(Exception, match="append-only"):
            db.execute(text("UPDATE repayments SET amount = 1"))
            db.commit()

    def test_repayment_cannot_be_deleted(self, paid_loan, db):
        with pytest.raises(Exception, match="append-only"):
            db.execute(text("DELETE FROM repayments"))
            db.commit()
