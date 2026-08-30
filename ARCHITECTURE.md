# Architecture — MicroLoan Demo

> How the system is put together, and *why* each boundary exists.
> Companion documents: [DOMAIN.md](DOMAIN.md) (the rules), [DATABASE.md](DATABASE.md) (the tables), [API.md](API.md) (the endpoints).

---

## 1. The one-sentence version

A FastAPI backend owns all business rules and all database access; a Next.js frontend is a
thin, server-rendered view over that API; and every money calculation lives in a layer of
**pure Python functions that touch neither the database nor the clock**.

---

## 2. Stack

| Concern | Choice | Version |
|---|---|---|
| Backend framework | FastAPI | 0.115+ |
| Language (backend) | Python | 3.12 |
| ORM | SQLAlchemy 2.0 (typed `Mapped[]` declarative models) | 2.0+ |
| Migrations | Alembic | 1.13+ |
| Database | PostgreSQL | 18 |
| Frontend | Next.js App Router + TypeScript | 15 |
| Styling | Tailwind CSS (plain — no component library; ADR-017 as amended) | — |
| Validation | Pydantic v2 (request/response schemas) | 2.x |
| Password hashing | argon2 (`argon2-cffi`) | — |
| Tests | pytest + httpx `AsyncClient` | — |
| Local orchestration | Docker Compose (postgres + api + web) | — |

Rationale for each choice is recorded in [docs/DECISIONS.md](docs/DECISIONS.md).

---

## 3. Layers

Dependencies point **inward only**. An inner layer never imports an outer one.

```
 ┌─────────────────────────────────────────────────────────────┐
 │  web/  Next.js — pages, forms, tables, dashboard            │
 │        knows HTTP and nothing about SQL                     │
 └──────────────────────────┬──────────────────────────────────┘
                            │  HTTP + httpOnly cookie
 ┌──────────────────────────▼──────────────────────────────────┐
 │  api/app/routers/    thin: parse input, check role, delegate│
 │                      no business logic, no SQL              │
 ├─────────────────────────────────────────────────────────────┤
 │  api/app/services/   the transaction boundary               │
 │                      orchestrates: load → decide → persist  │
 ├─────────────────────────────────────────────────────────────┤
 │  api/app/domain/     PURE functions                         │
 │                      no DB, no I/O, no datetime.now()       │
 ├─────────────────────────────────────────────────────────────┤
 │  api/app/models/     SQLAlchemy tables — data shape only    │
 └──────────────────────────┬──────────────────────────────────┘
                            ▼
                      PostgreSQL 18
```

### 3.1 `domain/` — the part that matters

Every rule about money is a **pure function**: same inputs, same output, forever.

```python
def build_schedule(principal, annual_rate, term_count, frequency, start_date) -> list[ScheduleRow]
def penalty_due(installment, late_fee, grace_days, as_of) -> Decimal
def allocate(payment_amount, installments, as_of) -> list[Allocation]
```

Three consequences, and they are the point of the whole design:

1. **No hidden clock.** Nothing calls `date.today()`. The current date is always passed in
   as `as_of`. That means a test can ask "what did this loan owe on 2026-04-01?" and get a
   deterministic answer — and so can an auditor.
2. **No database.** These functions can be tested with plain values, no Postgres, no
   fixtures, in milliseconds. See [TESTING.md](TESTING.md).
3. **Hand-verifiable.** Every number the system displays can be reproduced on paper from
   the worked examples in [DOMAIN.md](DOMAIN.md). Nothing is a black box.

If you explain one thing about this codebase to your supervisor, explain this layer.

### 3.2 `services/` — the transaction boundary

A service function is the unit of work. **One service call = one database transaction.**

```python
def record_repayment(session, *, loan_id, amount, paid_on, actor) -> Repayment:
    with session.begin():          # ← opens here
        loan = _load_for_update(session, loan_id)
        plan = allocate(amount, loan.installments, as_of=paid_on)   # pure decision
        ...                        # writes
    # ← commits here, or nothing happened at all
```

Three operations write to more than one table and are therefore all-or-nothing:

| Operation | Tables written in one transaction |
|---|---|
| Disburse a loan | `loans` (status, dates) · `installments` (N rows) · `ledger_entries` · `audit_log` |
| Record a repayment | `repayments` · `repayment_allocations` · `installments` · `ledger_entries` · `audit_log` · possibly `loans` (auto-close) |
| Approve / reject | `loans` · `audit_log` |

The audit row is written **inside the same transaction as the change it records**. There is
no code path that changes a loan without leaving an audit trail, because a failure would
roll back both.

### 3.3 `routers/` — deliberately boring

A router does exactly four things: validate the request with a Pydantic schema, resolve the
current user, call one service function, and serialise the result. If a router contains an
`if` about business rules, it is in the wrong place.

```python
@router.post("/loans/{loan_id}/approve")
def approve_loan(loan_id: UUID,
                 user: User = Depends(require_role(Role.ADMIN)),
                 session: Session = Depends(get_session)) -> LoanOut:
    return loan_service.approve(session, loan_id=loan_id, actor=user)
```

### 3.4 `models/` — shape only

SQLAlchemy models declare columns, types, foreign keys, and constraints. No behaviour, no
computed business values. Money columns are `NUMERIC(14, 2)` mapped to Python `Decimal` —
**never** `float`, anywhere, at any layer.

---

## 4. Request lifecycle — `POST /repayments`

Follow one request through every file it touches:

| # | Where | What happens |
|---|---|---|
| 1 | `web/app/(app)/repayments/new/page.tsx` | Cashier submits the form (loan, amount, date, method). |
| 2 | `web/lib/api.ts` | `POST` to FastAPI, forwarding the `access_token` cookie. |
| 3 | `api/app/routers/repayments.py` | Pydantic validates `RepaymentCreate`; `require_role(CASHIER, ADMIN)` resolves the user from the JWT. |
| 4 | `api/app/services/repayment_service.py` | Opens the transaction. Loads the loan with its installments (`SELECT … FOR UPDATE`). |
| 5 | `api/app/services/repayment_service.py` | Guard rules: loan is `DISBURSED`; `paid_on` is not before `disbursed_on` and not in the future. |
| 6 | `api/app/domain/penalty.py` | For each unpaid installment, compute `penalty_due(..., as_of=paid_on)`. |
| 7 | `api/app/domain/allocation.py` | `allocate()` returns the full plan — which installment gets how much fee / interest / principal. **Pure. No writes yet.** |
| 8 | `api/app/services/repayment_service.py` | Reject with `AMOUNT_EXCEEDS_OUTSTANDING` if money is left over after every installment is satisfied. |
| 9 | `api/app/services/repayment_service.py` | Writes: `repayments` row, one `repayment_allocations` row per installment touched, increments on `installments`, one `ledger_entries` row, one `audit_log` row. |
| 10 | `api/app/services/repayment_service.py` | If every installment is now fully paid → `loans.status = CLOSED`, `closed_at` set. |
| 11 | — | Commit. Response: the receipt with its allocation breakdown. |
| 12 | `web/` | Redirect to the loan detail page; the schedule now shows updated paid amounts and the new outstanding balance. |

Note the shape: **all decisions happen before any write.** Steps 6–8 are pure; step 9
simply applies a plan that has already been validated.

---

## 5. Authentication and authorisation

```
POST /auth/login {email, password}
      │  argon2 verify
      ▼
  Set-Cookie: access_token=<JWT>; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800
      JWT claims: {"sub": <user_id>, "role": "ADMIN", "exp": …}
```

- The token is **httpOnly** — JavaScript cannot read it, so an XSS bug cannot steal a session.
- `web/middleware.ts` verifies the JWT signature to decide *which pages to render* — this is
  a UX convenience only.
- **FastAPI is the sole authority.** Every endpoint re-verifies the token and re-checks the
  role via `Depends(require_role(...))`. Deleting the frontend guard would change nothing
  about what a user is actually allowed to do.

### Roles and separation of duties

| Role | Can do |
|---|---|
| `OFFICER` | Register members, create loan applications, read everything |
| `ADMIN` | Everything, plus approve / reject loans, deactivate members, read the audit log |
| `CASHIER` | Disburse approved loans, record repayments, read everything |

One rule cuts across all of them: **the person who created a loan may never approve it** —
including an ADMIN. See rule R1 in [DOMAIN.md](DOMAIN.md).

---

## 6. Frontend

Server Components do the reading; Server Actions / route handlers do the writing.

```
web/
  middleware.ts          route gating from the JWT (UX only)
  app/
    login/               the only public page
    (app)/
      layout.tsx         nav shell, current user, sign-out
      dashboard/         5 metric cards
      members/           table + search      members/new/    registration form
      loans/             table + status filter
                         loans/new/         form + live schedule preview
                         loans/[id]/        schedule, role-gated actions
                                                (approve / reject / disburse / record repayment)
  components/            loan-form.tsx (the one client component with live preview)
  lib/api.ts             single typed fetch wrapper — the ONLY place that knows the API URL
  lib/actions.ts         server actions — every write, one error path
  lib/format.ts          money formatting (2 decimals, always)
```

Deliberately thin (ADR-017, as amended): no member-detail page, no repayments browser,
no audit-log UI — the API docs at :8000/docs cover those. Repayment browsing, receipts,
and the audit log remain fully available through the API.

Every network call goes through `lib/api.ts`. There is no `fetch()` scattered through
components, so error handling, cookie forwarding, and the base URL each exist in one place.

---

## 7. Backend folder map

```
api/
  app/
    main.py              FastAPI app, CORS, exception handlers, startup lifespan
    bootstrap.py         startup: create database → alembic upgrade head → seed
    config.py            settings from environment (pydantic-settings)
    db.py                engine, session factory, get_session dependency
    security.py          argon2 hashing, JWT encode/decode, require_role
    seeds.py             the demo data itself (staff logins + demo portfolio)
    models/              users, members, loans, installments, repayments,
                         repayment_allocations, ledger_entries, audit_log
    schemas/             Pydantic request/response models
    domain/              money.py  interest.py  schedule.py  penalty.py  allocation.py
    services/            member_service  loan_service  repayment_service
                         dashboard_service  audit.py
    routers/             auth  members  loans  repayments  dashboard  audit
  alembic/versions/      0001_init.py  (+ later migrations)
  tests/domain/          pure-function tests, no database
  tests/api/             integration tests against a throwaway Postgres
  seed.py                CLI wrapper around app/seeds.py — seeding by hand
```

### Startup — how the database comes to exist

Running the API is the whole procedure (ADR-018). `app/main.py` has a lifespan that calls
`bootstrap.prepare_database()` before the first request is served:

```
uvicorn starts
   │
   ├─ wait for Postgres to accept connections      (native runs; compose gates on a healthcheck)
   ├─ CREATE DATABASE microloan   … if missing     AUTO_CREATE_DATABASE
   ├─ alembic upgrade head        … if behind      AUTO_MIGRATE
   └─ ensure staff logins, load the portfolio      AUTO_SEED
      … if the database has no members yet
   │
   ▼
Application startup complete.
```

Every step is idempotent, so a restart finds nothing to do and says so:

```
INFO:     schema is at revision 0001
INFO:     seed: 3 staff logins verified; portfolio already present
```

The schema is created by **Alembic, never by `Base.metadata.create_all()`** — the
append-only triggers, the partial unique index behind R2, and the trigram index exist only
in the migration, so a metadata-built schema would silently lack them
([DATABASE.md](DATABASE.md) §4).

---

## 8. Deliberate non-goals

Listed so that scope creep is visible rather than accidental:

payment reversal / void · savings accounts · multiple branches · multiple currencies ·
document or photo upload · nominee / guarantor records · reducing-balance (EMI) interest ·
SMS or email notification · date-range filters on the dashboard · frontend tests ·
background jobs of any kind.

Each of these is a deliberate omission for the trial demo, not an oversight.
