"""Dashboard figures match their own definition — the ledger and the source
tables agree, because the dashboard reads from the same rows."""

from decimal import Decimal

from sqlalchemy import text


class TestDashboard:
    def test_metrics_have_the_five_documented_fields(self, clients):
        body = clients.cashier.get("/dashboard/metrics").json()
        assert set(body) == {
            "members_total",
            "loans_active",
            "disbursed_total",
            "collected_total",
            "outstanding_total",
        }
        assert isinstance(body["members_total"], int)
        assert isinstance(body["loans_active"], int)

    def test_money_figures_match_the_ledger_and_repayments(self, clients, db):
        body = clients.admin.get("/dashboard/metrics").json()

        disbursed = db.execute(
            text("SELECT COALESCE(SUM(amount),0)::numeric FROM ledger_entries WHERE entry_type='DISBURSEMENT'")
        ).scalar_one()
        collected = db.execute(
            text("SELECT COALESCE(SUM(amount),0)::numeric FROM repayments")
        ).scalar_one()

        assert Decimal(body["disbursed_total"]) == disbursed
        assert Decimal(body["collected_total"]) == collected

    def test_outstanding_excludes_closed_loans(self, clients, db):
        body = clients.admin.get("/dashboard/metrics").json()
        outstanding = db.execute(
            text(
                """
                SELECT COALESCE(SUM(i.amount_due - i.principal_paid - i.interest_paid),0)::numeric
                FROM installments i JOIN loans l ON l.id = i.loan_id
                WHERE l.status = 'DISBURSED'
                """
            )
        ).scalar_one()
        assert Decimal(body["outstanding_total"]) == outstanding
