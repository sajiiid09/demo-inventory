# MicroLoan Demo

A small, deliberately simple loan-management system: register members, apply for a loan,
approve it, disburse it, collect repayments, and watch the balances update themselves.

Built as a trial for a larger project. The goals, in order: **clean code**, **a transparent
database**, and **simplicity that can be explained out loud**. Every non-obvious decision has
a written reason in [docs/DECISIONS.md](docs/DECISIONS.md).

> **Status: design complete, implementation not started.** These documents define what will
> be built. The build order is in [PLAN.md](PLAN.md).

---

## Features, mapped to the brief

| Requirement | Where it lives |
|---|---|
| Member registration and listing | `POST /members`, `GET /members` with search |
| Loan creation | `POST /loans` — with a live schedule preview that writes nothing |
| Loan approval | `POST /loans/{id}/approve` — ADMIN only, and never by the loan's creator |
| Loan disbursement | `POST /loans/{id}/disburse` — CASHIER; generates the repayment schedule |
| Per-customer parameters | Loan amount, interest rate, term, frequency, late fee, grace days |
| Automatic totals and schedule | Total payable, installment amount, and every due date, computed at disbursement |
| Repayment management | Partial payments, multi-installment payments, early settlement |
| Automatic balance updates | Each payment is allocated to specific installments; outstanding follows |
| Dashboard | Total members, active loans, total disbursed, total collections, total outstanding |
| Search and view | Members, loans, and repayments — all searchable, all with detail pages |
| Role-based login | `ADMIN` / `OFFICER` / `CASHIER`, with real separation of duties |

---

## Documentation

Eight short documents, each with one job.

| File | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The layers, the boundaries, and one request traced end to end |
| [DOMAIN.md](DOMAIN.md) | The loan rules and the arithmetic, with worked examples you can check by hand |
| [DATABASE.md](DATABASE.md) | Every table and constraint, plus the exact SQL behind every dashboard number |
| [API.md](API.md) | Endpoints, roles, payloads, and the error contract |
| [PLAN.md](PLAN.md) | The phased build order, with an exit criterion per phase |
| [TESTING.md](TESTING.md) | What is tested and why — a named checklist, not an essay |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Twelve decisions, each with the alternatives that were rejected |

**Reading it cold?** [DOMAIN.md](DOMAIN.md) §6 first — one worked loan, start to finish.
Everything else is machinery around those numbers.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic |
| Database | PostgreSQL 18 |
| Frontend | Next.js 15 (App Router) · TypeScript · Tailwind · shadcn/ui |
| Tests | pytest |
| Local run | Docker Compose |

---

## Running it

**Prerequisites:** Docker and Docker Compose. (Node 20 and Python 3.12 only if you want to
run the apps outside containers.)

```bash
cp .env.example .env
docker compose up
```

Then, in a second terminal, create the schema and load demo data:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python seed.py
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres | `localhost:5432`, database `microloan` |

### Demo logins

Seeded by `seed.py`. **Demo credentials only — never use these anywhere real.**

| Role | Email | Password |
|---|---|---|
| Admin | `admin@demo.local` | `demo1234` |
| Officer | `officer@demo.local` | `demo1234` |
| Cashier | `cashier@demo.local` | `demo1234` |

### Running the tests

```bash
cd api
pytest tests/domain -q     # the arithmetic — fast, no database needed
pytest -q                  # everything, including API integration tests
```

---

## What to look at first

1. **`api/app/domain/`** — the whole system in five small files. Pure functions: no database,
   no I/O, and no `date.today()` anywhere. Every money rule is here, and every one of them
   can be checked on paper.
2. **`api/app/services/repayment_service.py`** — the most interesting transaction. Note the
   shape: every decision is made *before* the first write.
3. **`api/alembic/versions/0001_init.py`** — the partial unique index enforcing one active
   loan per member, and the triggers that make the payment ledger physically append-only.
4. **[DOMAIN.md](DOMAIN.md) §6** — a 100,000.00 BDT loan over 24 weekly installments,
   worked out to the paisa.

---

## The one-minute explanation

A member applies for a loan. The officer enters the amount, rate, term, and frequency, and
the system shows the total payable and the exact installment before anything is saved. An
admin approves it — but never their own application. A cashier disburses it, and *that* is
when the repayment schedule becomes real rows in the database, anchored to the date the money
actually left.

From then on, every payment is broken down and recorded against specific installments:
this much to a late fee, this much to interest, this much to principal. Nothing is ever
overwritten or deleted — the payment ledger is append-only and the database enforces it.
So any balance on any date can be reconstructed from the record, and the dashboard's five
numbers are each one query you can run yourself.
