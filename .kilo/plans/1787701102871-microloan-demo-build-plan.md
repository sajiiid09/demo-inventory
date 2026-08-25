# MicroLoan Demo — Implementation Plan

> Build the system exactly as the eight documents in the repo describe, with four
> authorized deviations recorded in §2. The documents are the spec; this plan is the
> execution order. When code and docs disagree, the implementer stops and reconciles
> the two rather than guessing.

---

## 1. Context

- Repo `/Users/sajidmahmud/Documents/demo-inventory` contains **documentation only** —
  no code. Status line in README.md says "design complete, implementation not started."
- The spec: README.md, ARCHITECTURE.md, DOMAIN.md, DATABASE.md, API.md, PLAN.md,
  TESTING.md, docs/DECISIONS.md (17 ADRs). Read order for the implementer:
  DOMAIN.md → DATABASE.md → API.md → ARCHITECTURE.md.
- Stack (fixed by ADR-001/008/010): Python 3.12, FastAPI, SQLAlchemy 2.0 typed
  `Mapped[]` models, Alembic, PostgreSQL 18, pytest; Next.js 15 App Router +
  TypeScript + Tailwind. One repo, `api/` + `web/`, root `docker-compose.yml`.
- Toolchain verified on this machine: docker, python3.12, node, npm, uv (all in PATH).
  Docker **daemon** state unverified (command not permitable in plan mode).
- Priorities confirmed by the user: clean dataset, clean schemas, clean backend models.
  Frontend minimal. Not production-ready. Simplicity over rigor wherever the two clash.

## 2. Authorized deviations from the documents

1. **Frontend is thinner than PLAN.md Phase 8 / ADR-017.** Pages kept: login, members
   list + new, loans list + new (with live schedule preview), loan detail with
   role-gated Approve / Reject / Disburse / Record-repayment, dashboard (5 cards).
   Pages dropped: member detail, repayments list + receipt, audit-log UI (all
   reachable via Swagger at :8000/docs). **No shadcn/ui** — plain Tailwind tables,
   forms, and cards.
2. **Test suite is rules-focused, not exhaustive.** Full domain suite as documented.
   API suite: one test per rule R1–R6 (the coverage table in TESTING.md §4), both
   worked examples end-to-end, the DOMAIN.md §9 allocation case, atomic disbursement,
   auto-close, repayment append-only triggers, and the invariants check. Skipped:
   RBAC permutations beyond one 403 per role boundary, auth edge cases, search
   specifics, dashboard per-metric tests.
3. **Commit per phase.** Message format: `Phase N — <name>: <exit criterion met>`.
4. **Run strategy.** `docker-compose.yml` exactly as documented (postgres + api + web)
   is the final demo start. During development, run only Postgres in Docker and the
   API, tests, and web app natively (uv / npm).

Phase 9 amends README.md, PLAN.md, TESTING.md, and ADR-017 to record deviations 1–2
so the docs describe the system as actually built (their own stated requirement).

## 3. Phases

Each phase ends with: exit criterion met, `git status` reviewed, one commit.

### Phase 0 — Skeleton and infrastructure
- Verify Docker daemon (`docker info`). If down: start Docker Desktop/colima; if
  unresolvable, proceed with the documented fallback (Postgres-only container) and
  note it in the commit message.
- `docker-compose.yml`: `postgres:18`, `api` (uvicorn, reload), `web` (next dev),
  healthchecks, one `demo` network. Volumes for pgdata.
- `api/` via uv: `pyproject.toml` (fastapi, sqlalchemy 2.0, alembic, pydantic-settings,
  argon2-cffi, pyjwt, psycopg[binary], pytest, pytest-asyncio, httpx as dev deps),
  `app/main.py` with `/health`, `app/config.py` (pydantic-settings: DB URL, JWT
  secret, cookie name, CORS origin `http://localhost:3000`), `.env.example`.
- `web/` via create-next-app (TypeScript, Tailwind, App Router). **Do not init shadcn.**
- Root `.gitignore` (python, node, .env, .venv, .next).
- **Exit:** `docker compose up` healthy; `curl localhost:8000/health` → `{"status":"ok"}`;
  `localhost:3000` renders. README run instructions work from scratch.

### Phase 1 — Schema (skills: supabase-postgres-best-practices, clean-code)
- `api/app/models/` — all eight tables exactly per DATABASE.md §2: users, members,
  loans, installments, repayments, repayment_allocations, ledger_entries, audit_log.
  Typed `Mapped[]` declarative. Money = `Numeric(14,2)` ↔ `Decimal`. Enums:
  `user_role`, `member_status`, `loan_status`, `loan_frequency`, `payment_method`,
  `ledger_entry_type`, `ledger_direction`. Shape only — no behavior on models.
- `alembic/versions/0001_init.py` — tables + FKs + **hand-written**: all CHECK
  constraints from DATABASE.md §3, partial unique index `one_active_loan_per_member`,
  `reject_mutation()` + 4 append-only triggers (DATABASE.md §3.1). Working
  `downgrade()` dropping everything in reverse.
- `api/scripts/check_invariants.sql` — the six invariant checks from DATABASE.md §4
  as one query.
- **Exit:** `alembic upgrade head` on empty DB produces complete schema;
  `downgrade base` clean; `UPDATE repayments …` in psql raises
  `Table repayments is append-only`.

### Phase 2 — Domain, test-first (skill: clean-code) ⭐ the heart
- Write `api/tests/domain/` FIRST per TESTING.md §2 (all cases: money, interest,
  schedule, penalty, allocation — including both worked examples and the ~30-shape
  parametrized `SUM(amount_due) == total_payable` invariant).
- Then `api/app/domain/` until green: `money.py` (`q2` HALF_UP, `split_with_remainder`),
  `interest.py` (flat), `schedule.py` (`build_schedule`, `due_dates` with month-end
  clamp from the original day, last row absorbs both remainders), `penalty.py`
  (`penalty_due`), `allocation.py` (`allocate` fee→interest→principal, oldest first).
- Purity rules enforced: no imports from models/services/SQLAlchemy, no I/O, no
  `date.today()` — `as_of` always a parameter.
- **Exit:** `pytest tests/domain -q` green in <1s; example A (105,538.46 / 4,397.44 /
  last row 4,397.34) and example B (112,000.00 / 9,333.33 / last row 9,333.37)
  reproduce to the paisa.

### Phase 3 — Auth and RBAC (skill: clean-code)
- `security.py`: argon2 hash/verify, JWT (claims `sub`, `role`, `exp`; 8h),
  `get_current_user`, `require_role(*roles)`.
- Router `/auth`: login (sets `access_token` httpOnly SameSite=Lax cookie),
  logout, me. Identical 401 message for bad password / inactive user.
- `audit.py` helper `record(session, actor, action, entity, before, after)` — same
  transaction as the change. Action names exactly per DATABASE.md §2.8.
- Error contract: one exception family → `{detail: {code, message}}` per API.md §1,
  registered as FastAPI exception handlers. Money serialized as strings (Pydantic).
- CORS: allow `http://localhost:3000`, credentials true.
- **Exit:** three roles log in; CASHIER → approve = `403 FORBIDDEN`; expired token =
  `401 UNAUTHENTICATED`; login writes `USER_LOGGED_IN` audit row.

### Phase 4 — Members (skill: clean-code)
- `member_service` + router + Pydantic schemas: create (server-assigned `M-000001`
  sequential codes), list/search (`q` over name/phone/code, `status`, pagination),
  detail, `PATCH /{id}/status`.
- Duplicate phone/national_id → `409 DUPLICATE_FIELD` (catch IntegrityError, never
  leak it); deactivating a member with APPROVED/DISBURSED loan → `409 INVALID_STATE`.
- **Exit:** duplicates return clean 409s; search by all three fields works;
  deactivate-with-active-loan refused.

### Phase 5 — Loan lifecycle (skill: clean-code)
- `POST /loans/preview` — calls `build_schedule` directly, writes nothing (assert
  row counts unchanged in a test).
- `loan_service`: create (R2 check, `L-000001` codes), approve (R1 self-approval
  block incl. ADMIN, R2), reject (reason required), disburse — one transaction:
  freeze totals, N installment rows, DISBURSEMENT ledger entry, audit row.
  Guards R3 (state) and R5 (dates: `disbursed_on >= applied_on`, not future).
- `GET /loans` (filters status/member/q, pagination), `GET /loans/{id}` (terms,
  totals, dates, people, schedule with computed row status + accrued fees per
  API.md §5).
- **Exit:** disbursement atomic under forced failure (no installments/ledger, loan
  still APPROVED); officer cannot approve own loan; second active loan → 409 at
  service AND via partial index.

### Phase 6 — Repayments (skill: clean-code)
- `repayment_service.record` in the documented order: load loan `FOR UPDATE` →
  guard R3/R5 → pure `penalty_due` + `allocate` → guard R6 (message carries exact
  settlement figure) → write repayments, allocations, installment increments,
  ledger entry, audit row → auto-close (`CLOSED`, `closed_at`) when settled.
- `R-000001` receipt numbers; `GET /repayments`, `GET /repayments/{id}` (receipt
  with allocation breakdown); `GET /loans/{id}/settlement-quote`.
- **Exit:** DOMAIN.md §9 case (10,000.00 → 3 allocation lines, outstanding
  95,538.46) reproduces through the API; overpayment rejected with the figure;
  settling payment closes the loan; `check_invariants.sql` clean afterwards.

### Phase 7 — Dashboard (skill: clean-code)
- `dashboard_service` — the five queries from DATABASE.md §5 **verbatim**;
  `GET /dashboard/metrics`.
- **Exit:** the five numbers equal the same queries run by hand in psql against the
  seeded DB (spot-check three of them).

### Phase 8 — Thin frontend (skills: next-best-practices, vercel-react-best-practices;
  react-doctor afterwards)
- `lib/api.ts` — single typed fetch wrapper (base URL, cookie forwarding, one error
  path). `lib/format.ts` — BDT money (2 decimals, always) + date formatting.
- `/login` (form → POST /auth/login) + `middleware.ts` route gating (UX only).
- App shell: nav, current user, role-aware menu.
- `/members` list + search + new; `/loans` list + status filter; `/loans/new` with
  **live preview** calling `POST /loans/preview`; `/loans/[id]` — terms, schedule
  table (with accrued fees), role-gated action buttons (Approve/Reject/Disburse/
  Record repayment as inline form); `/dashboard` — five metric cards.
- Server Components for reads; route handlers/Server Actions for writes. No
  client-state libraries. No shadcn.
- **Exit:** full flow clickable without Swagger: register member → create loan →
  approve as ADMIN → disburse as CASHIER → record partial repayment → dashboard
  numbers move.

### Phase 9 — Seed, API tests, docs pass
- `seed.py`: 3 demo users (README credentials), ~20 members, loans in **every**
  status incl. one overdue past grace and one closed — fixed dates so the demo is
  identical every run. Idempotent (truncate-and-reload or version guard).
- `api/tests/api/` — the rules-focused suite from §2 deviation 2, against a
  throwaway `microloan_test` DB migrated once per session; tests use fixed dates,
  never `date.today()`.
- Docs pass: amend README (frontend description), PLAN.md Phase 8, TESTING.md scope,
  ADR-017 (Tailwind-only, thin flow) so all documents match what was built. Remove
  README's "implementation not started" status line.
- **Exit:** fresh clone runs with two commands; `pytest` green; DOMAIN.md §6 numbers
  findable in the running app; `check_invariants.sql` returns zero violations on the
  seeded DB.

## 4. Definition of done (trial)

1. `docker compose up` + migrate + seed → demo runs.
2. R1–R6 enforced, each with a passing named test.
3. Both DOMAIN.md worked examples reproduce exactly in the running system.
4. `check_invariants.sql` → zero violations on seeded data.
5. Every state change appears in the audit log with the correct actor.
6. The documents describe the system as actually built (deviations recorded).

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Docker daemon not running/unavailable | Phase 0 verifies; fallback = Postgres-only container + native uv/npm (already confirmed installed) |
| Cookie auth across :3000 ↔ :8000 (PLAN.md flags this medium) | CORS with credentials + SameSite=Lax cookie, decided in Phase 3; verify from the browser early via /login, not at Phase 8 |
| `postgres:18` image unavailable | Fallback `postgres:17`; record in commit message + README |
| Money drift via float anywhere | Decimal end-to-end, money-as-string over the wire; grep for `float` in review each backend phase |
| Autogenerate misses partial index/triggers | They are hand-written in `0001_init` per PLAN.md; downgrade tested |
| Scope creep toward production concerns | ARCHITECTURE.md §8 non-goals + §2 deviations are the contract; reject additions |

## 6. Explicitly out of scope

Everything in ARCHITECTURE.md §8 (reversals, savings, branches, multi-currency,
uploads, nominees, EMI interest, notifications, dashboard filters, frontend tests,
background jobs) **plus**: member detail page, repayments/receipt pages, audit-log UI,
shadcn/ui, charts, exhaustive test permutations, performance work, deployment.
