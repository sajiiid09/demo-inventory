# Database — MicroLoan Demo

> Every table, every constraint, and the exact SQL behind every number on the dashboard.
> PostgreSQL 18. Migrations are Alembic revisions in `api/alembic/versions/`.

**Design principles for this schema**

1. **Money is `NUMERIC(14,2)`** mapped to Python `Decimal`. `float` appears nowhere.
2. **The ledger is append-only.** Repayments and their allocations can never be updated or
   deleted — a database trigger refuses it, not just application code.
3. **Rules live in the database where they can.** Uniqueness, non-negative amounts, and the
   one-active-loan-per-member rule are constraints, not just Python `if` statements.
4. **Nothing is deleted, ever.** Members are deactivated, loans are rejected or closed.

---

## 1. Entity relationships

```
users ──┬──created_by──▶ members ──┬──▶ loans ──┬──▶ installments
        │                          │            │        ▲
        ├──created_by/approved_by/─┘            │        │ installment_id
        │  disbursed_by ───────────▶            │        │
        │                                       ├──▶ repayments ──▶ repayment_allocations
        │                                       │                          │
        │                                       └──▶ ledger_entries        │
        │                                                                  │
        └──actor_user_id──▶ audit_log                    (links payment ⇄ schedule row)
```

---

## 2. Tables

### 2.1 `users`

Staff accounts. There is no self-registration — users are seeded or created by an ADMIN.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK, `gen_random_uuid()` |
| `email` | `text` | no | **UNIQUE**, lower-cased on write |
| `password_hash` | `text` | no | argon2id. The plaintext is never stored or logged. |
| `full_name` | `text` | no | |
| `role` | `user_role` | no | `ADMIN` \| `OFFICER` \| `CASHIER` |
| `is_active` | `boolean` | no | default `true`; inactive users cannot log in |
| `created_at` | `timestamptz` | no | default `now()` |

### 2.2 `members`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `member_code` | `text` | no | **UNIQUE**, `M-000001`, sequential, never reused |
| `full_name` | `text` | no | |
| `phone` | `text` | no | **UNIQUE** |
| `national_id` | `text` | no | **UNIQUE** |
| `address` | `text` | yes | |
| `joined_on` | `date` | no | |
| `status` | `member_status` | no | `ACTIVE` \| `INACTIVE`, default `ACTIVE` |
| `created_by` | `uuid` | no | → `users.id` |
| `created_at` | `timestamptz` | no | default `now()` |

Index on names for search: `members_full_name_trgm` (a trigram GIN index, via the
`pg_trgm` extension, created in migration `0001_init`). Phone search rides the unique
constraint's own index — a separate `members_phone_idx` would be redundant.

### 2.3 `loans`

The terms columns (`total_interest`, `total_payable`, `installment_amount`) are `NULL`
until disbursement, then frozen forever — see rule R4 in [DOMAIN.md](DOMAIN.md).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `loan_code` | `text` | no | **UNIQUE**, `L-000001` |
| `member_id` | `uuid` | no | → `members.id` |
| `principal` | `numeric(14,2)` | no | the amount requested |
| `interest_rate_annual` | `numeric(5,2)` | no | percent per year, flat, e.g. `12.00` |
| `term_count` | `integer` | no | number of installments |
| `frequency` | `loan_frequency` | no | `WEEKLY` \| `MONTHLY` |
| `late_fee` | `numeric(14,2)` | no | flat fee per overdue installment, default `0.00` |
| `grace_days` | `integer` | no | default `3` |
| `total_interest` | `numeric(14,2)` | yes | frozen at disbursement |
| `total_payable` | `numeric(14,2)` | yes | frozen at disbursement |
| `installment_amount` | `numeric(14,2)` | yes | nominal; the last row differs by the remainder |
| `status` | `loan_status` | no | `PENDING` \| `APPROVED` \| `REJECTED` \| `DISBURSED` \| `CLOSED` |
| `applied_on` | `date` | no | |
| `created_by` | `uuid` | no | → `users.id` — the officer. Used to enforce R1. |
| `approved_by` | `uuid` | yes | → `users.id` |
| `approved_at` | `timestamptz` | yes | |
| `rejection_reason` | `text` | yes | required when status is `REJECTED` |
| `disbursed_on` | `date` | yes | anchors every due date |
| `disbursed_by` | `uuid` | yes | → `users.id` — the cashier |
| `closed_at` | `timestamptz` | yes | set automatically when the last installment is paid |

### 2.4 `installments`

The repayment schedule. Rows exist only for `DISBURSED` and `CLOSED` loans.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `loan_id` | `uuid` | no | → `loans.id` |
| `seq` | `integer` | no | 1 … `term_count`; **UNIQUE (loan_id, seq)** |
| `due_date` | `date` | no | |
| `principal_due` | `numeric(14,2)` | no | |
| `interest_due` | `numeric(14,2)` | no | |
| `amount_due` | `numeric(14,2)` | no | `= principal_due + interest_due` |
| `principal_paid` | `numeric(14,2)` | no | default `0.00` |
| `interest_paid` | `numeric(14,2)` | no | default `0.00` |
| `fee_paid` | `numeric(14,2)` | no | default `0.00` |

Installment status (`PENDING` / `PARTIAL` / `PAID`) is **derived, not stored** — it is a
function of `principal_paid + interest_paid` versus `amount_due`. Storing it would create a
second source of truth that could drift.

### 2.5 `repayments` — append-only

One row per payment received. This is the money-in record.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `receipt_no` | `text` | no | **UNIQUE**, `R-000001` |
| `loan_id` | `uuid` | no | → `loans.id` |
| `amount` | `numeric(14,2)` | no | `CHECK (amount > 0)` |
| `paid_on` | `date` | no | the date the money was received — drives fee calculation |
| `method` | `payment_method` | no | `CASH` \| `BANK` \| `MOBILE` |
| `note` | `text` | yes | |
| `received_by` | `uuid` | no | → `users.id` — the cashier |
| `created_at` | `timestamptz` | no | default `now()` |

### 2.6 `repayment_allocations` — append-only

**This is the transparency table.** It answers "which payment paid which installment, and
how was it split?" for every taka in the system.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `repayment_id` | `uuid` | no | → `repayments.id` |
| `installment_id` | `uuid` | no | → `installments.id`; **UNIQUE (repayment_id, installment_id)** |
| `fee_amount` | `numeric(14,2)` | no | default `0.00` |
| `interest_amount` | `numeric(14,2)` | no | default `0.00` |
| `principal_amount` | `numeric(14,2)` | no | default `0.00` |

### 2.7 `ledger_entries` — append-only

Every movement of money in one place. The dashboard money totals read from here and nowhere
else, so the two figures on screen can never disagree with each other.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `entry_type` | `ledger_entry_type` | no | `DISBURSEMENT` \| `REPAYMENT` |
| `direction` | `ledger_direction` | no | `OUT` for disbursement, `IN` for repayment |
| `loan_id` | `uuid` | no | → `loans.id` |
| `amount` | `numeric(14,2)` | no | `CHECK (amount > 0)` |
| `occurred_on` | `date` | no | `disbursed_on` or `paid_on` — the business date |
| `source_id` | `uuid` | no | the `loans.id` or `repayments.id` that caused it |
| `created_by` | `uuid` | no | → `users.id` |
| `created_at` | `timestamptz` | no | default `now()` |

### 2.8 `audit_log`

Written **inside the same transaction** as the change it records. If the change rolls back,
so does the audit row; if the audit row fails, so does the change.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK |
| `actor_user_id` | `uuid` | no | → `users.id` |
| `action` | `text` | no | `MEMBER_CREATED`, `LOAN_CREATED`, `LOAN_APPROVED`, `LOAN_REJECTED`, `LOAN_DISBURSED`, `REPAYMENT_RECORDED`, `LOAN_CLOSED`, `MEMBER_DEACTIVATED`, `USER_LOGGED_IN` |
| `entity_type` | `text` | no | `member` \| `loan` \| `repayment` \| `user` |
| `entity_id` | `uuid` | no | |
| `before` | `jsonb` | yes | null on create |
| `after` | `jsonb` | yes | null on delete (which never happens) |
| `occurred_at` | `timestamptz` | no | default `now()` |

Index: `audit_log_entity_idx (entity_type, entity_id, occurred_at DESC)`.

---

## 3. Constraints and integrity

These are the lines to show a reviewer. Each one moves a rule out of application code and
into the database, where it holds even if the application is bypassed.

```sql
-- R2: one active loan per member — enforced by Postgres, not by Python.
CREATE UNIQUE INDEX one_active_loan_per_member
    ON loans (member_id)
    WHERE status IN ('APPROVED', 'DISBURSED');

-- Money is never negative, and a loan is never for nothing.
ALTER TABLE loans        ADD CONSTRAINT loans_principal_positive CHECK (principal > 0);
ALTER TABLE loans        ADD CONSTRAINT loans_term_positive      CHECK (term_count > 0);
ALTER TABLE loans        ADD CONSTRAINT loans_rate_non_negative  CHECK (interest_rate_annual >= 0);
ALTER TABLE repayments   ADD CONSTRAINT repayments_amount_positive CHECK (amount > 0);
ALTER TABLE installments ADD CONSTRAINT installments_paid_non_negative
    CHECK (principal_paid >= 0 AND interest_paid >= 0 AND fee_paid >= 0);

-- An installment can never be overpaid on principal or interest.
ALTER TABLE installments ADD CONSTRAINT installments_not_overpaid
    CHECK (principal_paid <= principal_due AND interest_paid <= interest_due);

-- A rejected loan must say why; a disbursed loan must have its frozen terms.
ALTER TABLE loans ADD CONSTRAINT loans_rejection_has_reason
    CHECK (status <> 'REJECTED' OR rejection_reason IS NOT NULL);
ALTER TABLE loans ADD CONSTRAINT loans_disbursed_has_terms
    CHECK (status NOT IN ('DISBURSED', 'CLOSED')
           OR (disbursed_on IS NOT NULL AND total_payable IS NOT NULL));

-- R5: money cannot leave before it was applied for.
ALTER TABLE loans ADD CONSTRAINT loans_disbursed_after_applied
    CHECK (disbursed_on IS NULL OR disbursed_on >= applied_on);
```

### 3.1 The append-only ledger

```sql
CREATE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only; % is not permitted',
                    TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER repayments_append_only
    BEFORE UPDATE OR DELETE ON repayments
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE TRIGGER allocations_append_only
    BEFORE UPDATE OR DELETE ON repayment_allocations
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE TRIGGER ledger_append_only
    BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();

CREATE TRIGGER audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION reject_mutation();
```

A recorded payment is a historical fact. It cannot be edited or deleted by the application,
by a developer with a psql prompt, or by a mistake. (Payment reversal is a deliberate
non-goal for v1 — see [ARCHITECTURE.md](ARCHITECTURE.md) §8. When it is added, it will be a
*reversing entry*, not an edit.)

### 3.2 An honest note on the active-loan index

The partial index covers `APPROVED` and `DISBURSED` only. That means **two `PENDING`
applications for the same member can coexist** — which is intentional, since an application
is only a request. Approving the second one is what gets refused:

1. `loan_service.approve()` checks first and returns a clean `409 MEMBER_HAS_ACTIVE_LOAN`.
2. If that check were ever bypassed, the unique index raises and the transaction aborts.

The service check exists for the error message; the index exists for the guarantee.

---

## 4. Invariants

Properties that must hold after every transaction. Each has a test in [TESTING.md](TESTING.md).

| Invariant | SQL check |
|---|---|
| A schedule sums to the loan total | `SUM(installments.amount_due) = loans.total_payable` per disbursed loan |
| A payment is fully allocated | `SUM(fee + interest + principal) = repayments.amount` per repayment |
| Installments are never overpaid | enforced by `installments_not_overpaid` |
| Paid amounts match allocations | `installments.principal_paid = SUM(allocations.principal_amount)` for that installment |
| Ledger matches source records | `SUM(ledger IN) = SUM(repayments.amount)` and `SUM(ledger OUT) = SUM(loans.principal WHERE disbursed)` |
| A closed loan owes nothing | `status = 'CLOSED'` ⟹ every installment fully paid |

A `scripts/check_invariants.sql` file runs all six as one query — useful to run live during
the demo to prove the books balance.

---

## 5. Dashboard SQL

The five metrics from the brief. Each is one query, written out here so that any number on
screen can be defended and reproduced in psql.

```sql
-- 1. Total members (active only)
SELECT COUNT(*) AS members_total
FROM members
WHERE status = 'ACTIVE';

-- 2. Active loans
SELECT COUNT(*) AS loans_active
FROM loans
WHERE status = 'DISBURSED';

-- 3. Total disbursed
SELECT COALESCE(SUM(amount), 0)::numeric(14,2) AS disbursed_total
FROM ledger_entries
WHERE entry_type = 'DISBURSEMENT';

-- 4. Total collections
SELECT COALESCE(SUM(amount), 0)::numeric(14,2) AS collected_total
FROM ledger_entries
WHERE entry_type = 'REPAYMENT';

-- 5. Total outstanding (principal + interest still owed on active loans)
SELECT COALESCE(SUM(i.amount_due - i.principal_paid - i.interest_paid), 0)::numeric(14,2)
       AS outstanding_total
FROM installments i
JOIN loans l ON l.id = i.loan_id
WHERE l.status = 'DISBURSED';
```

**Two things to say out loud when demonstrating this:**

- `outstanding_total` counts **principal and interest only**. Accrued late fees are excluded
  because they are computed on read and are not a receivable until they are charged. Fees are
  shown per loan on the loan detail page instead.
- `collected_total` is all-time and includes fee payments, so
  `disbursed_total − collected_total` is **not** the same as `outstanding_total`. They answer
  different questions: cash movement versus contractual balance.

---

## 6. Migrations

- One Alembic revision per schema change; `0001_init` creates everything above, including
  the enums, the partial index, the check constraints, and the append-only triggers.
- Revisions are hand-reviewed after autogeneration — autogenerate does not produce partial
  indexes or triggers, so those are written by hand.
- `alembic upgrade head` on an empty database must produce the complete schema. That is the
  exit criterion for phase 1 in [PLAN.md](PLAN.md).
- Every revision has a working `downgrade()`.
- **`Base.metadata.create_all()` is never used.** The triggers in §3.1, the partial unique
  index in §3.2, and the trigram index in §2.2 cannot be expressed as model declarations, so
  a metadata-built schema would look correct and silently lack all three. Alembic is the only
  thing that creates this schema — including the copy the API builds for itself on startup,
  and the throwaway database the test suite builds (ADR-018).

---

## 7. How the schema gets created

Nothing to run by hand: **starting the API creates the database and its tables.**
`app/bootstrap.py` runs inside the FastAPI lifespan, before the first request is served.

| Step | What it does | Switch | Skipped when |
|---|---|---|---|
| 1 | Waits for Postgres to accept connections | — | it already does |
| 2 | `CREATE DATABASE microloan` | `AUTO_CREATE_DATABASE` | the database exists |
| 3 | `alembic upgrade head` | `AUTO_MIGRATE` | already at head (a no-op) |
| 4 | Ensures the three staff logins | `AUTO_SEED` | never — drift is repaired every boot |
| 5 | Loads the demo portfolio | `AUTO_SEED` | the database already has members |

Each switch is an environment variable, default `true`. Set any of them to `false` in an
environment that provisions its database out of band. The boot logs what it did:

```
INFO:     created database 'microloan'
INFO:     schema is at revision 0001
INFO:     seed: 3 staff logins · 20 members (1 INACTIVE) · 8 loans in every status …
```

Step 5 runs only into an empty portfolio because the ledger is append-only (§3.1) — demo
data cannot be layered on top of itself. To start over:

```bash
docker compose down -v && docker compose up      # drops the volume, rebuilds everything
```

Or, against a database you are keeping:

```bash
cd api && alembic downgrade base && alembic upgrade head && python seed.py
```

---

## 8. Browsing the database in pgAdmin or DBeaver

The Postgres container publishes port **5433** on the host (5432 is deliberately left free
for any local Postgres you already run), so any client connects to it directly.

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5433` |
| Database | `microloan` |
| Username | `microloan` |
| Password | `123` |
| SSL mode | `disable` / `prefer` (it is a local container) |

**DBeaver:** Database → New Database Connection → PostgreSQL → fill in the table above →
Test Connection → Finish. The tables are under `microloan ▸ Schemas ▸ public ▸ Tables`.

**pgAdmin:** right-click Servers → Register → Server. On the *General* tab give it a name;
on the *Connection* tab use the table above. The tables are under
`Servers ▸ <name> ▸ Databases ▸ microloan ▸ Schemas ▸ public ▸ Tables`.

A few things worth opening once you are connected, because they are the parts a screenshot
cannot show:

- **`loans` ▸ Constraints** — the five check constraints from §3, including
  `loans_rejection_has_reason` and `loans_disbursed_after_applied`.
- **`loans` ▸ Indexes ▸ `one_active_loan_per_member`** — the partial unique index with its
  `WHERE status IN ('APPROVED','DISBURSED')` clause. This *is* rule R2 (§3.2).
- **`repayments` ▸ Triggers** — the `BEFORE UPDATE OR DELETE` trigger that makes the ledger
  physically append-only. Try `UPDATE repayments SET amount = 1;` in a SQL editor and read
  the error it raises.
- **`installments`** for one disbursed loan, ordered by `seq` — the schedule, with the last
  row carrying the rounding remainder (DOMAIN.md §6).

No psql needed, but if you prefer it:

```bash
docker compose exec postgres psql -U microloan -d microloan
```
