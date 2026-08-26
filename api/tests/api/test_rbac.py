"""RBAC boundaries — TESTING.md §3: one 403 per role boundary, every role reads."""

from tests.conftest import make_loan, make_member, unique


def _pending_loan(clients) -> dict:
    member = make_member(clients)
    return clients.officer.post(
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


class TestRbac:
    def test_officer_cannot_approve_loan(self, clients):
        loan = _pending_loan(clients)
        approve = clients.officer.post(f"/loans/{loan['id']}/approve")
        assert approve.status_code == 403
        assert approve.json()["detail"]["code"] == "FORBIDDEN"

    def test_cashier_cannot_approve_loan(self, clients):
        loan = _pending_loan(clients)
        approve = clients.cashier.post(f"/loans/{loan['id']}/approve")
        assert approve.status_code == 403
        assert approve.json()["detail"]["code"] == "FORBIDDEN"

    def test_officer_cannot_disburse_loan(self, clients):
        loan = _pending_loan(clients)
        clients.admin.post(f"/loans/{loan['id']}/approve")
        disburse = clients.officer.post(
            f"/loans/{loan['id']}/disburse", json={"disbursed_on": "2026-01-05"}
        )
        assert disburse.status_code == 403

    def test_officer_cannot_record_repayment(self, clients):
        loan = make_loan(clients)
        response = clients.officer.post(
            "/repayments",
            json={
                "loan_id": loan["id"],
                "amount": "100.00",
                "paid_on": "2026-01-13",
                "method": "CASH",
            },
        )
        assert response.status_code == 403

    def test_cashier_cannot_create_member(self, clients):
        response = clients.cashier.post("/members", json=unique())
        assert response.status_code == 403

    def test_non_admin_cannot_read_audit_log(self, clients):
        assert clients.officer.get("/audit-log").status_code == 403
        assert clients.cashier.get("/audit-log").status_code == 403
        assert clients.admin.get("/audit-log").status_code == 200

    def test_every_role_can_read_members_loans_repayments(self, clients):
        for client in (clients.admin, clients.officer, clients.cashier):
            assert client.get("/members").status_code == 200
            assert client.get("/loans").status_code == 200
            assert client.get("/repayments").status_code == 200
            assert client.get("/dashboard/metrics").status_code == 200
