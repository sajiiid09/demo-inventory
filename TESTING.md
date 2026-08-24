# Testing — MicroLoan Demo

> What is tested, why, and the exact list of cases. This file is a checklist, not an essay.
> Rules **R1–R6** are defined in [DOMAIN.md](DOMAIN.md) §3.

---

## 1. Strategy

Two suites, deliberately different in cost and purpose.

| Suite | Location | Needs a database? | Runtime | What it protects |
|---|---|---|---|---|
| **Domain** | `api/tests/domain/` | no | < 1 second | The arithmetic — schedules, fees, allocation |
| **API** | `api/tests/api/` | yes | seconds | The rules — roles, states, transactions |

The domain suite is large and cheap because the domain layer is pure: no database, no clock,
no I/O. The API suite is small and targeted — it tests *rules and boundaries*, not
arithmetic, because the arithmetic is already covered.

**No frontend tests** in v1. Recorded as a deliberate non-goal in
[ARCHITECTURE.md](ARCHITECTURE.md) §8.

### Tooling

- `pytest` + `pytest-asyncio`
- `httpx.AsyncClient` against the FastAPI app (no live server needed)
- A throwaway `microloan_test` database, created and migrated once per session
- Each test runs inside a transaction that is rolled back afterwards, so tests never see
  each other's data and order never matters
- Fixed dates everywhere. **No test ever calls `date.today()`** — `as_of` is always passed
  explicitly, which is only possible because the domain layer has no hidden clock

---

## 2. Domain tests — `tests/domain/`

### `test_money.py`

```
rounds_half_up_to_two_decimals              0.005 → 0.01, not banker's rounding
rounds_negative_values_consistently
split_with_remainder_sums_exactly           parametrized over many totals and n
split_with_remainder_puts_difference_last   only the last element differs
split_of_zero_returns_zeros
```

### `test_interest.py`

```
weekly_flat_interest_matches_worked_example   100,000 · 12% · 24 wk → 5,538.46
monthly_flat_interest_matches_worked_example  100,000 · 12% · 12 mo → 12,000.00
zero_rate_produces_zero_interest
interest_scales_linearly_with_term            flat interest is linear, by definition
```

### `test_schedule.py`

```
weekly_example_matches_documented_table       all 24 rows == DOMAIN.md §6
monthly_example_matches_documented_table      all 12 rows == DOMAIN.md §7
schedule_sums_exactly_to_total_payable        parametrized, ~30 loan shapes  ← INVARIANT
principal_rows_sum_to_principal
interest_rows_sum_to_total_interest
last_installment_absorbs_both_remainders
weekly_due_dates_step_by_seven_days
monthly_due_dates_step_by_one_month
monthly_due_date_clamps_to_month_end          31 Jan → 28 Feb → 31 Mar
monthly_due_date_clamps_in_leap_year          31 Jan 2028 → 29 Feb 2028
single_installment_loan_is_valid              n = 1 edge case
```

The `~30 loan shapes` case is the important one: awkward principals (`10,000.03`), awkward
terms (7, 13, 53 installments), and rates that produce long decimals. It asserts the money
never leaks — the rows always sum to the exact total.

### `test_penalty.py` — R-independent, pure

```
no_fee_on_a_paid_installment
no_fee_before_due_date
no_fee_on_the_due_date_itself
no_fee_on_last_day_of_grace                   as_of == due_date + grace_days
fee_applied_on_first_day_past_grace           due_date + grace_days + 1
fee_charged_once_and_never_compounds          same value 3 days late and 300 days late
zero_late_fee_configuration_produces_no_fee
```

### `test_allocation.py`

```
exact_installment_payment_settles_one_row
partial_payment_applies_to_oldest_installment
large_payment_cascades_across_installments    the 10,000.00 case from DOMAIN.md §9
allocation_order_is_fee_then_interest_then_principal
fee_is_consumed_before_interest_on_overdue_row
allocations_sum_to_payment_amount             ← INVARIANT, parametrized
payment_never_over_allocates_an_installment
full_settlement_covers_every_remaining_row
leftover_money_is_reported_not_silently_kept  (the signal that triggers R6)
```

---

## 3. API tests — `tests/api/`

### `test_auth.py`

```
login_sets_httponly_cookie
login_with_wrong_password_returns_401
login_of_inactive_user_returns_401_with_same_message   no user enumeration
request_without_cookie_returns_401
expired_token_returns_401
me_returns_current_user_and_role
login_writes_an_audit_row
```

### `test_rbac.py`

```
officer_cannot_approve_loan                   403 FORBIDDEN
cashier_cannot_approve_loan                   403 FORBIDDEN
officer_cannot_disburse_loan                  403 FORBIDDEN
officer_cannot_record_repayment               403 FORBIDDEN
cashier_cannot_create_member                  403 FORBIDDEN
non_admin_cannot_read_audit_log               403 FORBIDDEN
every_role_can_read_members_loans_repayments
```

### `test_members.py`

```
create_member_assigns_sequential_member_code
duplicate_phone_returns_409_duplicate_field           not a raw IntegrityError
duplicate_national_id_returns_409_duplicate_field
search_matches_partial_name_phone_and_member_code
cannot_deactivate_member_with_active_loan             409 INVALID_STATE
member_detail_includes_full_loan_history
```

### `test_loan_lifecycle.py`

```
preview_writes_nothing_to_the_database                row counts unchanged
preview_matches_documented_weekly_example
officer_cannot_approve_own_loan                       403 · R1
admin_cannot_approve_a_loan_they_created              403 · R1 applies to ADMIN too
cannot_create_second_loan_while_one_is_active         409 · R2
cannot_approve_second_loan_while_one_is_active        409 · R2
partial_index_blocks_second_active_loan               R2 at the database level
cannot_disburse_unapproved_loan                       409 · R3
cannot_disburse_twice                                 409 · R3
cannot_disburse_before_applied_on                     422 · R5
cannot_disburse_with_a_future_date                    422 · R5
reject_requires_a_reason                              422
rejected_loan_cannot_be_approved                      409 · R3
disbursement_generates_full_schedule                  N rows, sums to total_payable
disbursement_writes_ledger_and_audit_rows
disbursement_is_atomic                                forced failure → zero rows written
approved_loan_terms_cannot_be_edited                  405/409 · R4
```

### `test_repayment.py`

```
repayment_on_undisbursed_loan_is_rejected             409 · R3
repayment_before_disbursement_date_is_rejected        422 · R5
repayment_with_future_date_is_rejected                422 · R5
repayment_exceeding_outstanding_is_rejected           422 · R6, message carries the figure
partial_repayment_updates_installments_correctly      the DOMAIN.md §9 case, end to end
repayment_creates_one_allocation_per_touched_installment
repayment_writes_ledger_entry_and_audit_row
overdue_repayment_pays_the_fee_first
final_repayment_closes_the_loan                       status CLOSED, closed_at set
closed_loan_rejects_further_repayments                409 · R3
repayment_cannot_be_updated                           database trigger raises
repayment_cannot_be_deleted                           database trigger raises
settlement_quote_matches_a_settling_payment           quote then pay → loan closes
```

### `test_dashboard.py`

```
metrics_on_empty_database_return_zeros                not nulls
members_total_counts_only_active_members
loans_active_counts_only_disbursed_loans
disbursed_total_matches_ledger_sum
collected_total_matches_repayment_sum
outstanding_total_excludes_closed_loans
outstanding_total_excludes_accrued_fees               documented behaviour, asserted
```

### `test_invariants.py`

Runs after a scripted sequence of ~15 operations (register, apply, approve, disburse,
partial pay, overdue pay, settle) and asserts all six invariants from
[DATABASE.md](DATABASE.md) §4:

```
schedule_sums_to_total_payable_for_every_loan
allocations_sum_to_repayment_amount_for_every_receipt
installment_paid_amounts_match_their_allocations
no_installment_is_overpaid
ledger_totals_match_source_records
closed_loans_owe_nothing
```

---

## 4. Rule-to-test coverage

Every business rule has at least one test that names it. This table is the audit.

| Rule | Tests |
|---|---|
| **R1** creator cannot approve | `officer_cannot_approve_own_loan`, `admin_cannot_approve_a_loan_they_created` |
| **R2** one active loan | `cannot_create_second_loan_while_one_is_active`, `cannot_approve_second_loan_while_one_is_active`, `partial_index_blocks_second_active_loan` |
| **R3** status gating | `cannot_disburse_unapproved_loan`, `cannot_disburse_twice`, `repayment_on_undisbursed_loan_is_rejected`, `closed_loan_rejects_further_repayments`, `rejected_loan_cannot_be_approved` |
| **R4** frozen terms | `approved_loan_terms_cannot_be_edited`, `schedule_sums_to_total_payable_for_every_loan` |
| **R5** date ordering | `cannot_disburse_before_applied_on`, `cannot_disburse_with_a_future_date`, `repayment_before_disbursement_date_is_rejected`, `repayment_with_future_date_is_rejected` |
| **R6** no overpayment | `repayment_exceeding_outstanding_is_rejected`, `leftover_money_is_reported_not_silently_kept`, `settlement_quote_matches_a_settling_payment` |

---

## 5. Running the tests

```bash
docker compose up -d postgres
cd api
pytest tests/domain -q          # fast, no database, run this constantly while coding
pytest -q                       # everything
pytest --cov=app --cov-report=term-missing
```

**Coverage target:** 100% of `app/domain/` — it is pure and small, so there is no excuse for
a gap. Everything else is covered by consequence, not by target; chasing a global percentage
produces tests that assert nothing.

---

## 6. Manual demo verification

Automated tests do not replace walking the flow once before showing anyone. The script:

1. Log in as **OFFICER** → register a member → create a loan
   (100,000.00 · 12% · 24 weekly) → check the preview shows **105,538.46** total and
   **4,397.44** per installment.
2. Log in as **ADMIN** → approve it. Confirm the OFFICER's own account cannot.
3. Log in as **CASHIER** → disburse on `2026-01-05` → confirm 24 installments appear,
   the last one being **4,397.34**, and that they sum to **105,538.46**.
4. Record a **10,000.00** repayment → confirm the receipt shows three allocation lines and
   an outstanding balance of **95,538.46**.
5. Open the dashboard → confirm all five numbers moved as expected.
6. Log in as **ADMIN** → open the audit log → confirm every step above is listed with the
   right actor.
