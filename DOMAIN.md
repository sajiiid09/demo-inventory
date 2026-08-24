# Domain Rules — MicroLoan Demo

> The business logic, in plain language, with worked numbers you can check by hand.
> Everything here lives in `api/app/domain/` as pure functions. If a number on screen
> disagrees with this document, the code is wrong.

---

## 1. Vocabulary

These words mean exactly one thing each, everywhere in the code, the database, and the UI.
Never substitute a synonym.

| Term | Meaning |
|---|---|
| **Member** | A person registered with the organisation. May or may not have a loan. |
| **Loan** | One lending agreement with one member. Has a status and frozen terms. |
| **Installment** | One row of the repayment schedule: a due date and an amount owed. |
| **Repayment** | One payment event — money actually received, with a receipt number. |
| **Allocation** | The record of which repayment paid which installment, split into fee / interest / principal. |
| **Ledger entry** | An append-only record of money moving: `DISBURSEMENT` out, `REPAYMENT` in. |
| **Outstanding** | `amount_due − principal_paid − interest_paid`, summed over installments. Excludes fees. |
| **Accrued fee** | A late fee that a rule says is owed but that no payment has covered yet. Not stored. |
| **Total payable** | `principal + total_interest`. Frozen at disbursement. Never changes. |

Currency is **BDT** only. Every amount is stored and displayed with **exactly 2 decimal places**.

---

## 2. Loan lifecycle

```
                    ┌──────────────── reject(ADMIN, reason) ──────▶ REJECTED  ●
                    │
  create(OFFICER)   │
  ────────────▶  PENDING ──approve(ADMIN)──▶ APPROVED ──disburse(CASHIER)──▶ DISBURSED
                                                                                 │
                                                    every installment fully paid │
                                                                                 ▼
                                                                              CLOSED  ●
```

`●` = terminal. There is no path out of `REJECTED` or `CLOSED`.

| Transition | Who | What is written |
|---|---|---|
| create | OFFICER, ADMIN | `loans` row, status `PENDING`, `applied_on`, `created_by` |
| approve | ADMIN | `status = APPROVED`, `approved_by`, `approved_at` |
| reject | ADMIN | `status = REJECTED`, `rejection_reason` |
| disburse | CASHIER, ADMIN | `status = DISBURSED`, `disbursed_on`, `disbursed_by`, the frozen totals, **all N installment rows**, one ledger entry |
| close | *(automatic)* | `status = CLOSED`, `closed_at` — never triggered by a human |

**Loan terms cannot be edited after approval.** To change an amount or a rate, reject the
application and create a new one. This keeps the audit trail honest.

---

## 3. Business rules

Numbered so that tests and error codes can cite them. See [TESTING.md](TESTING.md) —
every rule below has a test with a matching name.

| # | Rule | Error code if violated |
|---|---|---|
| **R1** | The user who created a loan may never approve it. This applies to ADMIN too. | `FORBIDDEN_SELF_APPROVAL` (403) |
| **R2** | A member may hold only one loan in `APPROVED` or `DISBURSED` at a time. | `MEMBER_HAS_ACTIVE_LOAN` (409) |
| **R3** | Only `APPROVED` loans can be disbursed. Only `DISBURSED` loans accept repayments. | `INVALID_STATE` (409) |
| **R4** | At disbursement, `total_interest`, `total_payable` and `installment_amount` are computed once and frozen. They are never recalculated afterwards. | — (invariant) |
| **R5** | `disbursed_on` may not precede `applied_on`. `paid_on` may not precede `disbursed_on` and may not be in the future. | `INVALID_DATE` (422) |
| **R6** | A repayment may not exceed the total outstanding plus accrued fees as of `paid_on`. The error carries the exact settlement figure. | `AMOUNT_EXCEEDS_OUTSTANDING` (422) |

R2 is not only enforced in code — the database itself refuses it. See the partial unique
index in [DATABASE.md](DATABASE.md).

---

## 4. Interest — flat rate

Interest is **flat**: it is calculated once on the original principal and never recalculated
as the balance falls.

```
interest = principal × annual_rate × (term_count / periods_per_year)
```

| Frequency | `periods_per_year` |
|---|---|
| `WEEKLY` | 52 |
| `MONTHLY` | 12 |

`term_count` is the **number of installments**, not a number of years.

```
total_payable      = principal + interest
installment_amount = total_payable / term_count      (rounded HALF_UP to 2dp)
```

> **Why flat and not reducing-balance (EMI)?** Flat interest is standard practice in
> microfinance and NGO lending across South Asia, and — more importantly for a demo — the
> arithmetic can be verified on paper in ten seconds. The trade-off is recorded in
> [docs/DECISIONS.md](docs/DECISIONS.md) (ADR-002).

---

## 5. Schedule generation

The schedule is generated **once, at disbursement** — because due dates depend on the date
the money actually left, which is not known at application time.

### 5.1 Amounts

1. Split `principal` evenly across `term_count` rows, rounded HALF_UP to 2dp.
2. Split `interest` evenly the same way.
3. **The final row absorbs both remainders**, so the rows sum to the exact total.

```
principal_due(last) = principal − (principal_due(row) × (n − 1))
interest_due(last)  = interest  − (interest_due(row)  × (n − 1))
amount_due(row)     = principal_due(row) + interest_due(row)
```

Guaranteed invariant: `SUM(amount_due) == total_payable`, exactly, to the paisa.

### 5.2 Due dates

| Frequency | Rule |
|---|---|
| `WEEKLY` | `due_date(n) = disbursed_on + (n × 7) days` |
| `MONTHLY` | `due_date(n) = disbursed_on + n months`, clamped to the end of a short month |

Month-end clamping: a loan disbursed on **31 January** has installment 1 due **28 February**
(29 February in a leap year), installment 2 due **31 March**. The day-of-month is not lost —
it is clamped per row from the original date, never carried forward from the clamped one.

---

## 6. Worked example A — weekly

> This is the canonical example. The same numbers appear in [TESTING.md](TESTING.md) and
> the seed data, so nothing can drift.

```
principal        100,000.00
annual_rate      12%  (flat)
term_count       24 installments
frequency        WEEKLY
disbursed_on     2026-01-05
late_fee            100.00     grace_days 3
```

**Totals**

```
interest    = 100,000.00 × 0.12 × (24 / 52) =   5,538.46
total       = 100,000.00 + 5,538.46         = 105,538.46
installment = 105,538.46 / 24 = 4,397.4358… →   4,397.44
```

**Per-row split**

```
principal per row = 100,000.00 / 24 = 4,166.6667… → 4,166.67
interest  per row =   5,538.46 / 24 =   230.7692… →   230.77
```

**Schedule** (rows 4–22 follow the same pattern as rows 1–3)

| # | Due date | Principal | Interest | Amount due |
|---:|---|---:|---:|---:|
| 1 | 2026-01-12 | 4,166.67 | 230.77 | 4,397.44 |
| 2 | 2026-01-19 | 4,166.67 | 230.77 | 4,397.44 |
| 3 | 2026-01-26 | 4,166.67 | 230.77 | 4,397.44 |
| … | … | … | … | … |
| 23 | 2026-06-15 | 4,166.67 | 230.77 | 4,397.44 |
| **24** | **2026-06-22** | **4,166.59** | **230.75** | **4,397.34** |
| | **Total** | **100,000.00** | **5,538.46** | **105,538.46** ✓ |

Check by hand: `23 × 4,397.44 = 101,141.12`, `+ 4,397.34 = 105,538.46`. Exact.

---

## 7. Worked example B — monthly

```
principal 100,000.00 · 12% flat/yr · 12 monthly installments · disbursed 2026-01-05

interest    = 100,000.00 × 0.12 × (12 / 12) =  12,000.00
total       =                                 112,000.00
installment = 112,000.00 / 12                =   9,333.33
```

| # | Due date | Principal | Interest | Amount due |
|---:|---|---:|---:|---:|
| 1 | 2026-02-05 | 8,333.33 | 1,000.00 | 9,333.33 |
| … | … | … | … | … |
| 11 | 2026-12-05 | 8,333.33 | 1,000.00 | 9,333.33 |
| **12** | **2027-01-05** | **8,333.37** | **1,000.00** | **9,333.37** |
| | **Total** | **100,000.00** | **12,000.00** | **112,000.00** ✓ |

Check by hand: `11 × 9,333.33 = 102,666.63`, `+ 9,333.37 = 112,000.00`. Exact.

---

## 8. Late fees

```python
def penalty_due(installment, late_fee, grace_days, as_of) -> Decimal:
    if installment.is_fully_paid:                       return Decimal("0.00")
    if as_of <= installment.due_date + grace_days:      return Decimal("0.00")
    return late_fee
```

- **Flat**, charged **once per overdue installment**. It does not grow with time and it
  never compounds.
- Configured **per loan** (`late_fee`, `grace_days`), not globally, so different products
  can behave differently later.
- **Computed on read, never accrued by a background job.** A fee becomes a database row only
  at the moment a repayment allocates money to it. There is no scheduler to run, nothing to
  go stale, and the answer for any date is reproducible forever.

**Boundary cases** — installment 3 of example A, due `2026-01-26`, `grace_days = 3`,
`late_fee = 100.00`:

| `as_of` | Penalty | Why |
|---|---:|---|
| 2026-01-26 | 0.00 | Due today, not yet late |
| 2026-01-29 | 0.00 | Last day of grace (`due + 3`) |
| 2026-01-30 | 100.00 | First day past grace |
| 2026-04-30 | 100.00 | Still 100.00 — the fee never compounds |
| any date, once paid | 0.00 | Paid installments never accrue |

Accrued fees are shown on the loan detail page. They are **not** included in the dashboard's
`outstanding_total`, which counts only principal and interest. See [DATABASE.md](DATABASE.md) §5.

---

## 9. Repayment allocation

A payment is not "applied to a loan" as a lump sum — it is allocated to specific
installments, and the split is stored. That is what makes every taka traceable.

**Algorithm**

1. Take the unpaid installments, oldest first (`ORDER BY due_date, seq`).
2. Within one installment, consume in this order: **accrued fee → interest → principal**.
3. Whatever is left over cascades to the next installment. Repeat until the money runs out.
4. If money remains after every installment is satisfied → reject the payment with
   `AMOUNT_EXCEEDS_OUTSTANDING` (rule R6) and return the exact settlement figure.
5. If every installment is now fully paid → the loan becomes `CLOSED`.

**Worked case** — a payment of **10,000.00** against example A, nothing paid yet, no fees due:

| Installment | Fee | Interest | Principal | Applied | Running total |
|---|---:|---:|---:|---:|---:|
| 1 | 0.00 | 230.77 | 4,166.67 | 4,397.44 | 4,397.44 |
| 2 | 0.00 | 230.77 | 4,166.67 | 4,397.44 | 8,794.88 |
| 3 | 0.00 | 230.77 | 974.35 | 1,205.12 | **10,000.00** |

Result: installments 1 and 2 are `PAID`; installment 3 is `PARTIAL` with `3,192.32` still
owed; three rows land in `repayment_allocations`. The sum of the allocations equals the
payment amount exactly — an invariant that is tested.

**With a fee**: if installment 1 were 5 days overdue, the first 100.00 of the payment would
go to the fee, leaving 9,900.00 for interest and principal. The fee is consumed first so
that a partial payer never quietly accrues more fees on an installment they are servicing.

---

## 10. Early settlement

Because interest is **flat**, `total_payable` is fixed at disbursement and never shrinks.
Settling a loan early means paying the remaining `amount_due` plus any accrued fees.
**There is no interest rebate.**

Worked case — example A, with installments 1–6 fully paid and installment 7 overdue past
its grace period:

```
GET /loans/{id}/settlement-quote?as_of=2026-03-01

outstanding      = 105,538.46 − (6 × 4,397.44) = 79,153.82
accrued_fees     =                                   100.00   (installment 7, one flat fee)
settlement_total =                               79,253.82
```

Pay exactly `settlement_total` on that date and the loan closes the same day.

> This is the most likely question you will be asked in a review. The honest answer: a
> reducing-balance product would rebate unearned interest; a flat product, by definition,
> does not. The choice is documented in ADR-002 and would be the first thing to revisit for
> the production system.

---

## 11. Member rules

| Field | Rule |
|---|---|
| `member_code` | Auto-generated, sequential, `M-000001` format. Never reused. |
| `phone` | Unique across all members. |
| `national_id` | Unique across all members. |
| `status` | `ACTIVE` on registration. ADMIN may set `INACTIVE`. |

- A member is **never deleted** — deactivate instead. History must stay intact.
- A member with an `APPROVED` or `DISBURSED` loan cannot be set `INACTIVE`.
- Only `ACTIVE` members can have a new loan application created.
- A member's total outstanding is the sum over their loans; with rule R2 in force, at most
  one of those is active at any time.
