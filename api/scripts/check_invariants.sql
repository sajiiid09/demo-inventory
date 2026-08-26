-- check_invariants.sql — run all six DATABASE.md §4 invariant checks as one query.
-- Every violations count must be 0. Run it live during the demo:
--   docker compose exec postgres psql -U microloan -d microloan -f /dev/stdin < api/scripts/check_invariants.sql
-- (or, from the api container: psql is not installed there — copy the file in.)

WITH bad_schedule_sums AS (
    -- A schedule sums to the loan total, per disbursed/closed loan
    SELECT l.id
    FROM loans l
    JOIN installments i ON i.loan_id = l.id
    WHERE l.status IN ('DISBURSED', 'CLOSED')
    GROUP BY l.id, l.total_payable
    HAVING SUM(i.amount_due) <> l.total_payable
),

bad_payment_sums AS (
    -- A payment is fully allocated
    SELECT r.id
    FROM repayments r
    JOIN repayment_allocations a ON a.repayment_id = r.id
    GROUP BY r.id, r.amount
    HAVING SUM(a.fee_amount + a.interest_amount + a.principal_amount) <> r.amount
),

overpaid_installments AS (
    -- Installments are never overpaid (also enforced by CHECK constraint)
    SELECT i.id
    FROM installments i
    WHERE i.principal_paid > i.principal_due
       OR i.interest_paid > i.interest_due
),

paid_amount_mismatches AS (
    -- Paid amounts match their allocations
    SELECT i.id
    FROM installments i
    LEFT JOIN repayment_allocations a ON a.installment_id = i.id
    GROUP BY i.id, i.principal_paid, i.interest_paid, i.fee_paid
    HAVING i.principal_paid <> COALESCE(SUM(a.principal_amount), 0)
        OR i.interest_paid  <> COALESCE(SUM(a.interest_amount), 0)
        OR i.fee_paid       <> COALESCE(SUM(a.fee_amount), 0)
),

bad_ledger AS (
    -- Ledger matches source records, both directions
    SELECT 1
    WHERE (SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE entry_type = 'REPAYMENT')
          <> (SELECT COALESCE(SUM(amount), 0) FROM repayments)
       OR (SELECT COALESCE(SUM(amount), 0) FROM ledger_entries WHERE entry_type = 'DISBURSEMENT')
          <> (SELECT COALESCE(SUM(principal), 0) FROM loans WHERE status IN ('DISBURSED', 'CLOSED'))
),

closed_loans_owing AS (
    -- A closed loan owes nothing
    SELECT l.id
    FROM loans l
    JOIN installments i ON i.loan_id = l.id
    WHERE l.status = 'CLOSED'
    GROUP BY l.id
    HAVING SUM(i.amount_due - i.principal_paid - i.interest_paid) > 0
)

SELECT 'schedule_sums_to_total_payable'        AS invariant, COUNT(*) AS violations FROM bad_schedule_sums
UNION ALL
SELECT 'allocations_sum_to_repayment_amount',  COUNT(*) FROM bad_payment_sums
UNION ALL
SELECT 'no_installment_overpaid',              COUNT(*) FROM overpaid_installments
UNION ALL
SELECT 'installment_paid_amounts_match_allocations', COUNT(*) FROM paid_amount_mismatches
UNION ALL
SELECT 'ledger_totals_match_source_records',   COUNT(*) FROM bad_ledger
UNION ALL
SELECT 'closed_loans_owe_nothing',             COUNT(*) FROM closed_loans_owing;
