"""The scripted end-to-end sequence, then all six DATABASE.md §4 invariants.

register → apply → approve → disburse → partial pay → overdue pay → settle,
then scripts/check_invariants.sql must report zero violations.
"""

from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from tests.conftest import make_member

INVARIANTS_SQL = (Path(__file__).parents[2] / "scripts" / "check_invariants.sql").read_text()


class TestInvariants:
    def test_scripted_sequence_leaves_the_books_balanced(self, clients, db):
        # 1 — register
        member = make_member(clients, full_name="Invariant Runner")

        # 2 — apply (the canonical terms)
        loan = clients.officer.post(
            "/loans",
            json={
                "member_id": member["id"],
                "principal": "100000.00",
                "interest_rate_annual": "12.00",
                "term_count": 24,
                "frequency": "WEEKLY",
                "late_fee": "100.00",
                "grace_days": 3,
                "applied_on": "2026-01-02",
            },
        ).json()

        # 3 — approve
        assert clients.admin.post(f"/loans/{loan['id']}/approve").status_code == 200

        # 4 — disburse
        assert clients.cashier.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-05"}
        ).status_code == 200

        # 5 — partial payment (within grace, no fees)
        assert clients.cashier.post(
            "/repayments",
            json={"loan_id": loan["id"], "amount": "10000.00", "paid_on": "2026-01-13", "method": "CASH"},
        ).status_code == 201

        # 6 — an overdue payment that consumes fees first
        assert clients.cashier.post(
            "/repayments",
            json={"loan_id": loan["id"], "amount": "600.00", "paid_on": "2026-02-01", "method": "CASH"},
        ).status_code == 201

        # 7 — settle with the live quote
        quote = clients.cashier.get(
            f"/loans/{loan['id']}/settlement-quote?as_of=2026-02-15"
        ).json()
        settle = clients.cashier.post(
            "/repayments",
            json={
                "loan_id": loan["id"],
                "amount": quote["settlement_total"],
                "paid_on": "2026-02-15",
                "method": "BANK",
            },
        )
        assert settle.status_code == 201, settle.text
        assert settle.json()["loan_status_after"] == "CLOSED"

        # the books must balance — all six invariant checks report zero
        rows = db.execute(text(INVARIANTS_SQL)).all()
        for invariant, violations in rows:
            assert violations == 0, f"{invariant} has {violations} violations"
        assert len(rows) == 6

    def test_allocations_always_sum_to_their_payment(self, clients, db):
        """Held for every repayment in the test database, not just ours."""
        mismatches = db.execute(
            text(
                """
                SELECT r.receipt_no
                FROM repayments r
                JOIN repayment_allocations a ON a.repayment_id = r.id
                GROUP BY r.id, r.receipt_no, r.amount
                HAVING SUM(a.fee_amount + a.interest_amount + a.principal_amount) <> r.amount
                """
            )
        ).all()
        assert mismatches == []
