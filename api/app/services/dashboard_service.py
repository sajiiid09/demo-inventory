"""The five dashboard metrics — DATABASE.md §5, verbatim.

Each number is exactly one SQL query, written out here so any figure on screen
can be reproduced in psql in front of the person asking.
"""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


def metrics(session: Session) -> dict:
    return {
        "members_total": session.execute(
            text(
                """
                SELECT COUNT(*) AS members_total
                FROM members
                WHERE status = 'ACTIVE';
                """
            )
        ).scalar_one(),
        "loans_active": session.execute(
            text(
                """
                SELECT COUNT(*) AS loans_active
                FROM loans
                WHERE status = 'DISBURSED';
                """
            )
        ).scalar_one(),
        "disbursed_total": session.execute(
            text(
                """
                SELECT COALESCE(SUM(amount), 0)::numeric(14,2) AS disbursed_total
                FROM ledger_entries
                WHERE entry_type = 'DISBURSEMENT';
                """
            )
        ).scalar_one(),
        "collected_total": session.execute(
            text(
                """
                SELECT COALESCE(SUM(amount), 0)::numeric(14,2) AS collected_total
                FROM ledger_entries
                WHERE entry_type = 'REPAYMENT';
                """
            )
        ).scalar_one(),
        "outstanding_total": session.execute(
            text(
                """
                SELECT COALESCE(SUM(i.amount_due - i.principal_paid - i.interest_paid), 0)::numeric(14,2)
                       AS outstanding_total
                FROM installments i
                JOIN loans l ON l.id = i.loan_id
                WHERE l.status = 'DISBURSED';
                """
            )
        ).scalar_one(),
    }
