# Build Plan — MicroLoan Demo

> The order in which this gets built, and how each phase proves it is finished.

---

## Build outcome (added after implementation)

Every phase 0–9 was completed with its exit criterion verified. Four deliberate
deviations from the plan above, agreed before implementation began:

1. **Phase 8 was built thinner than specified** (and ADR-017 amended to match):
   plain Tailwind, no shadcn/ui; the app covers login, members list + register,
   loans list + new with live preview, loan detail with role-gated actions, and
   the dashboard. Member detail, repayments pages, and audit-log UI were dropped —
   the API (and Swagger) serves them.
2. **The API test suite is rules-focused, not exhaustive**: one test per rule
   R1–R6, both worked examples, the §9 allocation case, disbursement atomicity,
   auto-close, the append-only triggers, and the invariants check — rather than
   all ~90 named cases in TESTING.md.
3. **Tests run sync** (starlette `TestClient`), not pytest-asyncio + httpx
   `AsyncClient` — simpler, same coverage.
4. **Postgres is published on host port 5433** (5432 is commonly taken by a
   local Postgres); containers talk internally regardless.

### Added after the plan

5. **The API migrates and seeds itself on startup** (ADR-018). The plan left
   `alembic upgrade head` and `python seed.py` as two manual steps after
   `docker compose up`; running only the first left a server that answered
   `/health` and returned `500` on everything else. `app/bootstrap.py` now runs
   both — plus `CREATE DATABASE` when the database itself is missing — inside
   the FastAPI lifespan, idempotently, with a switch per step. `seed.py` stayed
   as a CLI wrapper; the data moved to `app/seeds.py` so the app can import it.
   Covered by `tests/api/test_bootstrap.py`.
6. **The native Postgres on port 5432 is the default target**, not the container.
   The demo database sits in the developer's normal server list, next to their
   other databases, and is browsable in pgAdmin/DBeaver without a second
   connection. Docker Compose still works and still publishes its own Postgres
   on 5433 — deviation 4 above — so the two servers never collide; they simply
   hold separate copies of the data.

---

## Sequencing principle

**The arithmetic gets built and proven before anything is built on top of it.**

Phase 2 — the pure domain functions — comes before any endpoint, any screen, and any
database wiring. The risk in a lending system is not CRUD; it is a schedule that does not
sum to the total payable, or a payment allocated to the wrong installment. Those bugs are
invisible in a demo and expensive in production. So they get written first, in isolation,
with tests that run in milliseconds and need no database.

Everything after phase 2 is plumbing around a core that is already known to be correct.

---

## Phases

### Phase 0 — Skeleton and infrastructure

- `docker-compose.yml`: `postgres:18`, `api` (uvicorn, hot reload), `web` (next dev)
- `api/`: `pyproject.toml`, `app/main.py` with `/health`, `app/config.py` reading env
- `web/`: `create-next-app` with TypeScript, Tailwind, shadcn/ui initialised
- `.env.example` and `.gitignore`
- `README.md` run instructions verified from scratch

**Exit criterion** — `docker compose up` on a clean machine gives a healthy Postgres,
`curl localhost:8000/health` returns `200 {"status":"ok"}`, and `localhost:3000` renders.

---

### Phase 1 — Schema

- SQLAlchemy models for all eight tables in [DATABASE.md](DATABASE.md)
- Alembic revision `0001_init`: enums, tables, foreign keys, check constraints
- Hand-written into the same revision: the partial unique index
  `one_active_loan_per_member`, the `reject_mutation()` function, and the four append-only
  triggers (autogenerate will not produce these)
- `scripts/check_invariants.sql`

**Exit criterion** — `alembic upgrade head` on an empty database produces the complete
schema; `alembic downgrade base` removes it cleanly; `UPDATE repayments …` in psql raises
`Table repayments is append-only`.

---

### Phase 2 — Domain (the heart) ⭐

Pure functions in `api/app/domain/`, written test-first. No imports from `models/`,
`services/`, SQLAlchemy, or `datetime.now()`.

| Module | Contents |
|---|---|
| `money.py` | `q2()` (HALF_UP to 2dp), `split_with_remainder(total, n)` |
| `interest.py` | `flat_interest(principal, annual_rate, term_count, frequency)` |
| `schedule.py` | `build_schedule(...) -> list[ScheduleRow]`, `due_dates(...)` with month-end clamping |
| `penalty.py` | `penalty_due(installment, late_fee, grace_days, as_of)` |
| `allocation.py` | `allocate(amount, installments, as_of) -> list[Allocation]` |

**Exit criterion** — `pytest tests/domain` is green, including both worked examples from
[DOMAIN.md](DOMAIN.md) reproduced to the paisa, and a parametrised property test over ~30
loan shapes asserting `SUM(amount_due) == total_payable`.

---

### Phase 3 — Auth and RBAC

- `security.py`: argon2 hash/verify, JWT encode/decode, `get_current_user`,
  `require_role(*roles)`
- `POST /auth/login` sets the httpOnly cookie; `/auth/logout`; `/auth/me`
- `seed.py` creates the three demo users
- `audit.py` helper — `record(session, actor, action, entity, before, after)`

**Exit criterion** — all three roles log in; a CASHIER calling `/loans/{id}/approve` gets
`403 FORBIDDEN`; an expired token gets `401 UNAUTHENTICATED`; every login writes a
`USER_LOGGED_IN` audit row.

---

### Phase 4 — Members

- `member_service`: create (with `member_code` generation), list/search, detail, set status
- Router, Pydantic schemas, pagination helper

**Exit criterion** — a duplicate phone or national ID returns `409 DUPLICATE_FIELD` with a
readable message, not a raw `IntegrityError`; search by partial name, phone, and member code
all work; deactivating a member with an active loan is refused.

---

### Phase 5 — Loan lifecycle

- `POST /loans/preview` — calls `build_schedule` directly, writes nothing
- `loan_service.create` — R2 checked, `loan_code` generated
- `loan_service.approve` — R1 and R2, writes `approved_by` / `approved_at`
- `loan_service.reject` — reason required
- `loan_service.disburse` — **the first multi-table transaction**: freeze totals, insert N
  installments, insert the `DISBURSEMENT` ledger entry, insert the audit row
- `GET /loans`, `GET /loans/{id}` with computed statuses and accrued fees

**Exit criterion** — disbursement is atomic: with a forced failure injected after the
installment insert, the database is left with no installments, no ledger entry, and the loan
still `APPROVED`. An officer cannot approve their own loan. A second loan for the same member
is refused with `409`, and the partial index refuses it too if the service check is bypassed.

---

### Phase 6 — Repayments

- `repayment_service.record` — the second multi-table transaction, in this exact order:
  1. load the loan `FOR UPDATE`
  2. guard R3 and R5
  3. compute accrued fees (`penalty_due`) and the allocation plan (`allocate`) — **pure**
  4. guard R6
  5. write `repayments`, `repayment_allocations`, installment increments, ledger entry, audit row
  6. auto-close the loan if every installment is now settled
- `receipt_no` generation; `GET /repayments`, `GET /repayments/{id}`
- `GET /loans/{id}/settlement-quote`

**Exit criterion** — the worked allocation case from [DOMAIN.md](DOMAIN.md) §9 reproduces
exactly through the API; an overpayment is rejected with the correct settlement figure; a
settlement payment closes the loan and sets `closed_at`; `scripts/check_invariants.sql`
returns zero violations afterwards.

---

### Phase 7 — Dashboard

- `dashboard_service` running the five queries from [DATABASE.md](DATABASE.md) §5, verbatim
- `GET /dashboard/metrics`

**Exit criterion** — the five numbers match the same five queries run by hand in psql
against the seeded database.

---

### Phase 8 — Frontend

Built in this order so there is something clickable early:

1. `lib/api.ts` (typed fetch wrapper, cookie forwarding, one error path) + `lib/format.ts`
2. `/login` and `middleware.ts` route gating
3. App shell: nav, current user, role-aware menu
4. `/members` list + search, `/members/new`, `/members/[id]`
5. `/loans` list + status filter, `/loans/new` with a **live preview** of the schedule
6. `/loans/[id]` — terms, schedule table, allocations, and role-gated action buttons
   (Approve / Reject / Disburse / Record repayment)
7. `/repayments` list + search, `/repayments/[id]` receipt
8. `/dashboard` — five metric cards

**Exit criterion** — the full flow is clickable end to end without touching Swagger:
register a member → create a loan → approve as ADMIN → disburse as CASHIER → record a
partial repayment → watch the dashboard numbers change.

---

### Phase 9 — Seed data, integration tests, documentation pass

- `seed.py`: 3 users, ~20 members, loans in **every** status (pending, approved, rejected,
  disbursed with no payments, disbursed and partly paid, one overdue past grace, one closed),
  built from fixed dates so the demo looks the same every run
- `pytest tests/api` — the integration suite in [TESTING.md](TESTING.md)
- Re-read all eight documents against the built system; fix any drift

**Exit criterion** — a fresh clone runs with two commands, `pytest` is green, and every
number in [DOMAIN.md](DOMAIN.md) can be found in the running application.

---

## Sizing

| Phase | Relative effort | Risk |
|---|---|---|
| 0 Skeleton | S | low |
| 1 Schema | M | low |
| **2 Domain** | **M** | **high — this is where correctness is won or lost** |
| 3 Auth | S | medium (cookie/CORS setup between two origins) |
| 4 Members | S | low |
| 5 Loans | L | medium (transaction boundaries) |
| 6 Repayments | L | high (allocation + closure + invariants) |
| 7 Dashboard | S | low |
| 8 Frontend | L | low |
| 9 Seed + tests + docs | M | low |

Phases 0–7 are backend-only and can be demonstrated entirely through `/docs`. If time runs
short, phase 8 is the only phase that can be reduced without weakening the demonstration of
the engine.

---

## Definition of done for the trial

1. `docker compose up` and the demo runs.
2. All six business rules R1–R6 are enforced and have passing tests.
3. Both worked examples in [DOMAIN.md](DOMAIN.md) reproduce exactly in the running system.
4. `scripts/check_invariants.sql` returns zero violations against the seeded database.
5. Every state change appears in the audit log with the correct actor.
6. The eight documents describe the system as it actually was built.
