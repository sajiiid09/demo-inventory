# Demo Script — every feature, role by role

> A walkthrough you can read aloud while clicking. It assumes the stack is up and the seed
> data is untouched — either `cp .env.example .env && docker compose up`, or the pieces run
> separately (`docker compose up -d postgres`, then `uvicorn` and `npm run dev`; see
> [README.md](README.md)). Roughly **15 minutes** for the full run; the short version is
> Acts 1–4.

Two windows, side by side:

| | |
|---|---|
| **Web app** | http://localhost:3000 |
| **API docs** | http://localhost:8000/docs — everything the UI does not show |

The UI is deliberately thin (ADR-017). Where a step is API-only it is marked **[API]**, and
Swagger is the place to run it: click the endpoint → *Try it out* → *Execute*. Swagger shares
the browser's session cookie, so logging in through the web app logs you in there too.

**Logging in as a different role:** sign out from the header, or use a second browser
profile / private window so you can keep two roles open at once. That is worth doing — the
best moment in this demo is watching the same loan offer different buttons to different
people.

| Role | Email | Password |
|---|---|---|
| Officer | `officer@demo.local` | `demo1234` |
| Admin | `admin@demo.local` | `demo1234` |
| Cashier | `cashier@demo.local` | `demo1234` |

---

## The cast — what the seed data already contains

Fixed dates, identical on every machine. Have this table open; it saves hunting.

| Loan | Member | Status | Terms | What it demonstrates |
|---|---|---|---|---|
| `L-000001` | M-000002 Sultana Begum | PENDING | 40,000 · 12% · 16 weekly | An application waiting for a decision |
| `L-000002` | M-000002 Sultana Begum | PENDING | 25,000 · 10% · 12 weekly | Two applications may coexist (ADR-005) |
| `L-000003` | M-000003 Jahanara Imam | APPROVED | 60,000 · 12% · 12 monthly | Approved, waiting for the cashier |
| `L-000004` | M-000004 Abdul Karim | REJECTED | 90,000 · 15% · 24 weekly | A rejection, with its reason on the record |
| `L-000005` | M-000005 Mizanur Rahman | DISBURSED | 100,000 · 12% · 24 weekly | A full schedule, nothing paid yet |
| `L-000006` | M-000001 Rahim Uddin | DISBURSED | 100,000 · 12% · 24 weekly | Partly paid — the worked example in DOMAIN.md §9 |
| `L-000007` | M-000006 Shirin Akter | DISBURSED | 30,000 · 15% · 12 weekly | Overdue past grace — accrued late fees |
| `L-000008` | M-000007 Kamal Hossain | CLOSED | 20,000 · 10% · 8 weekly | Settled early, in one payment |

Plus **20 members**, one of them (`M-000008` Nasrin Sultana) deactivated with no loans.

---

## Act 1 — Officer: register a member and apply for a loan

**Sign in as `officer@demo.local`.**

### 1.1 The dashboard

Land on **Dashboard**. Five numbers, and each one is a single SQL query you can run yourself
— the exact statements are in [DATABASE.md](DATABASE.md) §5.

> Total members · Active loans · Total disbursed · Total collections · Total outstanding

Worth saying out loud: *outstanding* is principal + interest still owed. Accrued late fees
are deliberately **not** in it — a fee is not a receivable until it is charged
(DOMAIN.md §1).

### 1.2 Register a member

**Members → Register member.** Name, phone, national ID, address, joined date.

- Phone and national ID are **unique in the database**, not just checked in Python. Submit
  the same phone twice and the second attempt comes back
  `DUPLICATE_FIELD`, not a stack trace.
- The member code (`M-000021`) is assigned by the server, sequentially, and is never reused.
- Members are never deleted — only deactivated (ADR-016).

Back on **Members**, search by name or phone. Each row shows the member's active loan code
and their outstanding balance, so the list answers "who owes what" without a second click.

### 1.3 Apply for a loan — with the schedule shown before anything is saved

**Loans → New loan.** Pick the member you just created, then enter:

```
Principal          100000.00
Annual rate        12.00      (flat — ADR-002)
Term               24
Frequency          WEEKLY
Late fee           100.00     per overdue installment
Grace days         3
Applied on         today
```

**Stop before submitting.** The preview panel has already filled in:

| | |
|---|---|
| Total interest | 5,538.46 |
| Total payable | 105,538.46 |
| Per installment | 4,397.44 |

This is the point to make: **that preview wrote nothing.** It is `POST /loans/preview`,
a pure function over the numbers you typed (`app/domain/schedule.py`), with no database
access at all. Check the arithmetic on the spot:

```
interest = 100,000 × 12% × (24 weeks ÷ 52 weeks) = 5,538.46
total    = 105,538.46 ÷ 24 = 4,397.4358…  → 4,397.44 per installment
```

The last installment absorbs the rounding remainder, so the schedule sums to the total
exactly — never a paisa out. ([DOMAIN.md](DOMAIN.md) §6 works this loan through in full.)

Now **submit**. The loan is created `PENDING`. Note what it still has *no* values for:
`total_payable`, `installment_amount`, and any due dates. Those are not real yet — they are
frozen at disbursement, anchored to the day the money actually leaves (ADR-003).

### 1.4 The officer's ceiling

Open the loan you just created. **There is no Approve button.** Not hidden by CSS — the
officer has no route to it:

- **[API]** `POST /loans/{id}/approve` as the officer → `403 FORBIDDEN`,
  *"This action requires role ADMIN; you are OFFICER."*
- **[API]** `GET /audit-log` as the officer → `403 FORBIDDEN`.

The frontend gate is a convenience; FastAPI re-checks the role on every request and is the
only authority (ADR-007).

---

## Act 2 — Admin: approve, reject, and the rule that binds admins too

**Sign out. Sign in as `admin@demo.local`.**

### 2.1 Approve an application

**Loans → filter PENDING → `L-000001`** (Sultana Begum, 40,000). The status pills across the
top of the list are the filter; to find a specific loan by code or member name, add `?q=`
to the URL (`/loans?q=L-000001`) or use `GET /loans?q=…` — the list page keeps only the
status pills as visible controls.

The Approve and Reject buttons are here now, on the same page the officer just looked at.

Click **Approve**. Status → `APPROVED`, and the detail view now records *who* approved it and
*when*. Still no schedule: approval is a decision, not a disbursement.

### 2.2 Reject one, with a reason

Open **`L-000002`** (the same member's second application) and click **Reject** — the reason
box is required. Submit it empty and the API answers `VALIDATION_ERROR`.

The reason that is worth mentioning: the check is not only in the request schema. The
`loans_rejection_has_reason` check constraint on the `loans` table says
`status <> 'REJECTED' OR rejection_reason IS NOT NULL`. **A rejection without a reason cannot
exist in this database**, no matter which code path or SQL client tries to write one.

### 2.3 The best thirty seconds in the demo — R1, no self-approval

The loan **you** created in Act 1 was created by the officer, so as admin you can approve it.
Instead, create one *as the admin* and try to approve your own:

1. **Loans → New loan** — any member without an active loan, any terms. Submit.
2. Open it. **The Approve button is absent**, though you are an ADMIN and the loan is PENDING.
3. **[API]** Force it: `POST /loans/{id}/approve` → `403 FORBIDDEN_SELF_APPROVAL`.

> **The person who creates a loan can never approve it — including an admin.** Separation of
> duties is a property of the system, not of the org chart. (Rule R1, ADR-009.)

### 2.4 One active loan per member — enforced by Postgres

Sultana Begum now has an `APPROVED` loan. Try to create a second one for her.

- **UI:** the application is refused with `MEMBER_HAS_ACTIVE_LOAN`.
- **The point:** this is not a Python `if`. It is a **partial unique index** —
  `one_active_loan_per_member`, unique on `member_id` `WHERE status IN ('APPROVED','DISBURSED')`.
  Two concurrent requests cannot both slip through, and neither can someone writing directly
  to the database. (Rule R2, ADR-005 — visible in DBeaver under `loans ▸ Indexes`.)

Note the two `PENDING` applications she held before: *applications* may coexist. Only one may
become active.

### 2.5 The audit log — **[API]**

`GET /audit-log`. Every state change, newest first, with the actor's name and role and the
before/after JSON:

```
LOAN_APPROVED   Ayesha Rahman (ADMIN)   before {"status":"PENDING"}   after {"status":"APPROVED", …}
```

It is written **inside the same transaction as the change it records** — if the change rolls
back, so does its audit row. There is no path that changes state without leaving a trace.
Admin only.

### 2.6 Deactivate a member — **[API]**

`PATCH /members/{id}/status` with `{"status": "INACTIVE"}`. Nothing is deleted, here or
anywhere: `M-000008` in the seed data is the example.

---

## Act 3 — Cashier: release the money and collect it back

**Sign out. Sign in as `cashier@demo.local`.**

### 3.1 Disbursement is when the schedule becomes real

**Loans → filter APPROVED → `L-000003`** (Jahanara Imam, 60,000 · 12% · 12 **monthly**).
Enter a disbursement date and click **Disburse**.

Refresh the detail page. It has grown a **schedule**: twelve rows, `seq` 1…12, each with a
due date, principal due, interest due, and amount due.

Three things to point out:

1. **The due dates are anchored to the disbursement date**, not the application date and not
   the approval date. Money moved today, so instalment 1 is due one month from today.
2. **Monthly dates clamp to month end** — disburse on the 31st and February's due date is the
   28th (the 29th in a leap year), not a crash and not March 3rd.
3. **The terms are now frozen.** `total_payable` and `installment_amount` are written once,
   at this moment, and never recalculated. A rate change tomorrow cannot retroactively alter
   a loan that is already out (Rule R4).

Try to disburse it again → `INVALID_STATE`. Try a disbursement date *before* the application
date → `INVALID_DATE` (Rule R5, and the `loans_disbursed_after_applied` check constraint
backs it up in the database).

### 3.2 Record a repayment, and watch it get broken down

Open **`L-000005`** (Mizanur Rahman — disbursed, nothing paid, 105,538.46 outstanding). Its
instalments are 4,397.44 each. Record a payment of **10,000.00**.

The receipt that comes back is the whole point of this system:

| Instalment | Fee | Interest | Principal | |
|---|---|---|---|---|
| #1 | 0.00 | 230.77 | 4,166.67 | paid in full |
| #2 | 0.00 | 230.77 | 4,166.67 | paid in full |
| #3 | 0.00 | 230.77 | 974.35 | `PARTIAL` |

**Nothing is a lump sum.** 10,000 filled instalment 1, filled instalment 2, and part-filled
instalment 3 — and within each one the order is fixed: **fees, then interest, then
principal** (`app/domain/allocation.py`). Look at instalment 3: its interest was taken in
full (230.77) before a single paisa went to principal. The rows add up to exactly 10,000.00,
and an invariant check enforces that they always will (Act 4.2).

The outstanding balance on the loan, on the members list, and on the dashboard all follow
automatically — nothing is stored twice. This is the seeded state of `L-000006`, if you would
rather point at it than create it.

Now try to overpay: enter more than the settlement figure → `AMOUNT_EXCEEDS_OUTSTANDING`,
and the error message contains the exact amount that *would* settle it (Rule R6).

### 3.3 Late fees, computed rather than accrued

Open **`L-000007`** (Shirin Akter, 30,000 · 15% · 12 weekly, disbursed 2026-03-10, late fee
100.00, grace 3 days). Its due dates are well in the past, so the detail view shows
**accrued fees**.

There is no cron job and no nightly batch. `penalty_due(installment, late_fee, grace_days,
as_of)` is a pure function evaluated when you read the page (ADR-004), which means:

- the fee owed on *any* date, past or future, can be asked for and answered;
- there is no such thing as a "the job did not run last night" bug;
- and a fee only becomes money when a payment actually pays it.

Grace is real: an instalment 2 days overdue with `grace_days: 3` owes nothing.

### 3.4 Early settlement

**[API]** `GET /loans/{id}/settlement-quote?as_of=YYYY-MM-DD` on any disbursed loan:

```json
{ "as_of": "2026-09-01", "outstanding": "95538.46",
  "accrued_fees": "2200.00", "settlement_total": "97738.46" }
```

(That is `L-000006` — the accrued fees are the 22 instalments that are past their grace
window on that date, at 100.00 each. Ask for a different `as_of` and the fee figure moves
with it, because it was never stored.)

Pay exactly the settlement total and the loan closes itself — status `CLOSED`, `closed_at` stamped,
in the same transaction as the payment. `L-000008` in the seed data was settled this way,
in one payment.

Interest is flat, so there is **no rebate** for settling early: you pay the interest the loan
was written with. That is a stated decision, not an oversight (ADR-002, DOMAIN.md §10).

### 3.5 Receipts and history — **[API]**

- `GET /repayments` — every payment, searchable and paginated.
- `GET /repayments/{id}` — one receipt with its full allocation breakdown, the loan status
  after it, and the outstanding balance after it.

---

## Act 4 — The database, live

This is the part that separates the demo from a screenshot. Open **DBeaver** or **pgAdmin**:

| Host | Port | Database | User | Password |
|---|---|---|---|---|
| `localhost` | `5432` | `microloan` | `microloan` | `123` |

(Click-path for both tools: [DATABASE.md](DATABASE.md) §8.)

### 4.1 Try to rewrite history — and fail

Open a SQL editor on the `microloan` database:

```sql
UPDATE repayments SET amount = 1;
```

```
ERROR:  Table repayments is append-only; UPDATE is not permitted
CONTEXT:  PL/pgSQL function reject_mutation() line 3 at RAISE
```

`DELETE` fails the same way, and so do `repayment_allocations`, `ledger_entries`, and
`audit_log`. This is a `BEFORE UPDATE OR DELETE` trigger — not an application convention, not
an ORM setting. **A superuser with a SQL client cannot quietly alter the payment record**
(ADR-006). Corrections are new rows, never edits.

### 4.2 Prove the books balance

```bash
psql -d microloan -f api/scripts/check_invariants.sql
```

```
                 invariant                  | violations
--------------------------------------------+------------
 schedule_sums_to_total_payable             |          0
 allocations_sum_to_repayment_amount        |          0
 no_installment_overpaid                    |          0
 installment_paid_amounts_match_allocations |          0
 ledger_totals_match_source_records         |          0
 closed_loans_owe_nothing                   |          0
```

Six queries, run live, against whatever data the audience just created by clicking. Every
count must be `0`. Run it again after Act 3 and it still is.

### 4.3 Worth opening while you are in there

- `loans ▸ Indexes ▸ one_active_loan_per_member` — the partial unique index that **is** rule R2.
- `loans ▸ Constraints` — `loans_rejection_has_reason`, `loans_disbursed_after_applied`.
- `installments` for one disbursed loan, ordered by `seq` — the schedule, last row carrying
  the rounding remainder.
- `repayment_allocations` — the transparency table: which payment paid which instalment, split
  into fee / interest / principal.
- Any money column: `numeric(14,2)`. There is no `float` anywhere in this system, at any
  layer (ADR-008).

---

## Act 5 — The code, in five minutes

If the audience is technical, this is the closing argument.

| Open | Say |
|---|---|
| `api/app/domain/` — 5 files, ~300 lines | Every money rule. Pure functions: no database, no I/O, and **no `date.today()`** — `as_of` is always passed in. That is why the arithmetic is testable on paper and in CI (ADR-011). |
| `api/app/services/repayment_service.py` | The most interesting transaction. Note the shape: **every decision is made before the first write.** One service call = one transaction. |
| `api/alembic/versions/0001_init.py` | The partial unique index and the append-only triggers. Hand-written, because autogenerate cannot produce either. |
| `api/app/bootstrap.py` | Why starting the API is the whole runbook — and why it runs Alembic rather than `create_all()` (ADR-018). |
| `docs/DECISIONS.md` | Eighteen decisions, each with what was **rejected** and why. |

Then run the tests in front of them:

```bash
docker compose exec api pytest
```

```
240 passed
```

---

## Quick reference — who can do what

| Action | Officer | Admin | Cashier |
|---|:--:|:--:|:--:|
| Log in, read everything, dashboard | ✅ | ✅ | ✅ |
| Register / search members | ✅ | ✅ | — |
| Preview a schedule (writes nothing) | ✅ | ✅ | — |
| Create a loan application | ✅ | ✅ | — |
| Approve / reject a loan | — | ✅ | — |
| Approve a loan **they created** | — | ❌ **never** | — |
| Disburse an approved loan | — | ✅ | ✅ |
| Record a repayment | — | ✅ | ✅ |
| Deactivate a member | — | ✅ | — |
| Read the audit log | — | ✅ | — |

---

## If the demo data gets messy

Everything above is safe to run repeatedly except the one-way steps (a loan, once disbursed,
stays disbursed — that is the point). To get back to the exact starting state:

```bash
docker compose down -v && docker compose up
```

The `-v` drops the Postgres volume; the next boot recreates the database, migrates it, and
reseeds it with the same fixed dates. Roughly twenty seconds.
