"""Loan lifecycle rules R1–R5 plus disbursement atomicity — TESTING.md §3."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests.conftest import make_member

WEEKLY = {
    "principal": "100000.00",
    "interest_rate_annual": "12.00",
    "term_count": 24,
    "frequency": "WEEKLY",
    "late_fee": "100.00",
    "grace_days": 3,
    "applied_on": "2026-01-02",
}


def _create_loan(clients, body=None, member=None, by="officer"):
    member = member or make_member(clients)
    payload = {**WEEKLY, **(body or {}), "member_id": member["id"]}
    client = getattr(clients, by)
    response = client.post("/loans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _approve(clients, loan_id):
    response = clients.admin.post(f"/loans/{loan_id}/approve")
    assert response.status_code == 200, response.text


def _disburse(clients, loan_id, on="2026-01-05"):
    response = clients.cashier.post(f"/loans/{loan_id}/disburse", json={"disbursed_on": on})
    assert response.status_code == 200, response.text
    return response.json()


class TestPreview:
    def test_preview_writes_nothing_to_the_database(self, clients, db):
        before = db.execute(text("SELECT count(*) FROM loans")).scalar_one()
        response = clients.officer.post(
            "/loans/preview", json={**WEEKLY, "start_date": "2026-01-05"}
        )
        assert response.status_code == 200
        after = db.execute(text("SELECT count(*) FROM loans")).scalar_one()
        assert before == after

    def test_preview_matches_documented_weekly_example(self, clients):
        body = clients.officer.post(
            "/loans/preview", json={**WEEKLY, "start_date": "2026-01-05"}
        ).json()
        assert body["total_interest"] == "5538.46"
        assert body["total_payable"] == "105538.46"
        assert body["installment_amount"] == "4397.44"
        assert len(body["schedule"]) == 24
        assert body["schedule"][0]["amount_due"] == "4397.44"
        assert body["schedule"][-1]["amount_due"] == "4397.34"  # remainder absorbed
        assert sum(Decimal(r["amount_due"]) for r in body["schedule"]) == Decimal("105538.46")


class TestR1:
    def test_admin_cannot_approve_a_loan_they_created(self, clients):
        loan = _create_loan(clients, by="admin")  # admin is the creator here
        response = clients.admin.post(f"/loans/{loan['id']}/approve")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "FORBIDDEN_SELF_APPROVAL"


class TestR2:
    def test_cannot_create_second_loan_while_one_is_active(self, clients):
        member = make_member(clients)
        first = _create_loan(clients, member=member)
        _approve(clients, first["id"])
        _disburse(clients, first["id"])

        response = clients.officer.post("/loans", json={**WEEKLY, "member_id": member["id"]})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "MEMBER_HAS_ACTIVE_LOAN"

    def test_cannot_approve_second_loan_while_one_is_active(self, clients):
        member = make_member(clients)
        first = _create_loan(clients, member=member)
        second = _create_loan(clients, member=member)  # two PENDING may coexist
        _approve(clients, first["id"])
        _disburse(clients, first["id"])

        response = clients.admin.post(f"/loans/{second['id']}/approve")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "MEMBER_HAS_ACTIVE_LOAN"

    def test_partial_index_blocks_second_active_loan(self, clients, db):
        # Bypass the service entirely: the DATABASE refuses the second active loan.
        member = make_member(clients)
        loan = _create_loan(clients, member=member)
        _approve(clients, loan["id"])

        with pytest.raises(Exception, match="one_active_loan_per_member"):
            db.execute(
                text(
                    """
                    INSERT INTO loans (loan_code, member_id, principal,
                                       interest_rate_annual, term_count, frequency,
                                       applied_on, created_by, status,
                                       disbursed_on, total_payable)
                    SELECT 'L-TEST99', member_id, principal, interest_rate_annual,
                           term_count, frequency, applied_on, created_by, 'DISBURSED',
                           applied_on, principal
                    FROM loans WHERE id = CAST(:id AS uuid)
                    """
                ).bindparams(id=loan["id"])
            )
            db.commit()


class TestR3:
    def test_cannot_disburse_unapproved_loan(self, clients):
        loan = _create_loan(clients)  # PENDING
        response = clients.cashier.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-05"}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVALID_STATE"

    def test_cannot_disburse_twice(self, clients):
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        _disburse(clients, loan["id"])
        again = clients.cashier.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-06"}
        )
        assert again.status_code == 409

    def test_rejected_loan_cannot_be_approved(self, clients):
        loan = _create_loan(clients)
        clients.admin.post(
            f"/loans/{loan['id']}/reject", json={"reason": "Not enough capacity."}
        )
        response = clients.admin.post(f"/loans/{loan['id']}/approve")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "INVALID_STATE"


class TestR5:
    def test_cannot_disburse_before_applied_on(self, clients):
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        response = clients.cashier.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2025-12-31"}
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_DATE"

    def test_cannot_disburse_with_a_future_date(self, clients, monkeypatch):
        from app import clock

        monkeypatch.setattr(clock, "today", lambda: dt.date(2026, 1, 6))
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        response = clients.cashier.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-07"}
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_DATE"

    def test_reject_requires_a_reason(self, clients):
        loan = _create_loan(clients)
        response = clients.admin.post(f"/loans/{loan['id']}/reject", json={"reason": ""})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


class TestDisbursement:
    def test_disbursement_generates_full_schedule(self, clients):
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        body = _disburse(clients, loan["id"])
        assert body["status"] == "DISBURSED"
        assert len(body["schedule"]) == 24
        assert sum(Decimal(r["amount_due"]) for r in body["schedule"]) == Decimal("105538.46")
        assert body["totals"]["total_payable"] == "105538.46"

    def test_disbursement_writes_ledger_and_audit_rows(self, clients, db):
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        _disburse(clients, loan["id"])

        ledger = db.execute(
            text("SELECT entry_type, direction, amount FROM ledger_entries WHERE loan_id = :id"),
            {"id": loan["id"]},
        ).one()
        assert ledger.entry_type == "DISBURSEMENT"
        assert ledger.direction == "OUT"
        assert Decimal(ledger.amount) == Decimal("100000.00")

        audit_row = db.execute(
            text(
                "SELECT action FROM audit_log "
                "WHERE entity_id = :id AND action = 'LOAN_DISBURSED'"
            ),
            {"id": loan["id"]},
        ).one()
        assert audit_row is not None

    def test_disbursement_is_atomic(self, clients, db, monkeypatch):
        # Force a failure where the writes are already under way. With the audit
        # row raising, NOTHING may survive: no installments, no ledger, loan
        # still APPROVED. The transaction is all-or-nothing.
        loan = _create_loan(clients)
        _approve(clients, loan["id"])

        def boom(*args, **kwargs):
            raise RuntimeError("injected failure after the plan was applied")

        monkeypatch.setattr("app.audit.record", boom)

        from app.db import SessionLocal
        from app.models import User
        from app.services import loan_service

        cashier = db.query(User).filter_by(email="cashier@demo.local").one()

        session = SessionLocal()
        try:
            with pytest.raises(RuntimeError, match="injected failure"):
                loan_service.disburse(
                    session,
                    loan_id=loan["id"],
                    disbursed_on=dt.date(2026, 1, 5),
                    actor=cashier,
                )
        finally:
            session.rollback()
            session.close()

        check = db.execute(
            text(
                """
                SELECT (SELECT count(*) FROM installments WHERE loan_id = :id) AS rows_,
                       (SELECT count(*) FROM ledger_entries WHERE loan_id = :id) AS ledger,
                       (SELECT status FROM loans WHERE id = :id) AS status
                """
            ),
            {"id": loan["id"]},
        ).one()
        assert check.rows_ == 0
        assert check.ledger == 0
        assert check.status == "APPROVED"

    def test_approved_loan_terms_cannot_be_edited(self, clients):
        # R4 by construction: there is no PATCH /loans/{id} endpoint at all.
        loan = _create_loan(clients)
        _approve(clients, loan["id"])
        response = clients.admin.patch(f"/loans/{loan['id']}", json={"principal": "1.00"})
        assert response.status_code in (405, 409, 422)
