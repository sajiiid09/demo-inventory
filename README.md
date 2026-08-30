# MicroLoan Demo

A small, deliberately simple loan-management system: register members, apply for a loan,
approve it, disburse it, collect repayments, and watch the balances update themselves.

Built as a trial for a larger project. The goals, in order: **clean code**, **a transparent
database**, and **simplicity that can be explained out loud**. Every non-obvious decision has
a written reason in [docs/DECISIONS.md](docs/DECISIONS.md).

> **Status: implemented.** The build followed [PLAN.md](PLAN.md) phase by phase;
> the deviations from the original plan are recorded at the top of PLAN.md.

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
| Search and view | Members, loans, and repayments — all searchable via the API |
| Role-based login | `ADMIN` / `OFFICER` / `CASHIER`, with real separation of duties |

The web UI is deliberately thin (ADR-017, as amended): login, members list + register,
loans list + new with live preview, loan detail with role-gated actions, and the five
dashboard cards. Everything else — repayments browsing, receipts, the audit log, and every
edge case — is drivable from the API docs at `http://localhost:8000/docs`.

---

## Documentation

Nine short documents, each with one job.

| File | Read it for |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The layers, the boundaries, and one request traced end to end |
| [DOMAIN.md](DOMAIN.md) | The loan rules and the arithmetic, with worked examples you can check by hand |
| [DATABASE.md](DATABASE.md) | Every table and constraint, plus the exact SQL behind every dashboard number |
| [API.md](API.md) | Endpoints, roles, payloads, and the error contract |
| [PLAN.md](PLAN.md) | The phased build order, with an exit criterion per phase |
| [TESTING.md](TESTING.md) | What is tested and why — a named checklist, not an essay |
| [DEMO.md](DEMO.md) | A scripted walkthrough of every feature, role by role |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Eighteen decisions, each with the alternatives that were rejected |

**Reading it cold?** [DOMAIN.md](DOMAIN.md) §6 first — one worked loan, start to finish.
Everything else is machinery around those numbers.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic |
| Database | PostgreSQL 18 |
| Frontend | Next.js 15 (App Router) · TypeScript · Tailwind (plain — no component library) |
| Tests | pytest |
| Local run | Docker Compose |

---

## Running it

Two ways. **Running it natively is the default** — the apps run on your machine against the
Postgres you already have, which is what you want for hands-on QA. Docker Compose is there
for a one-command demo on a machine with nothing installed.

### Natively (the default)

**Prerequisites:** PostgreSQL 16+ running locally, Python 3.12, Node 20.

**One-time setup** — a role for the app on your Postgres. It gets `CREATEDB` so the API can
provision its own database on startup; you never create the database by hand:

```bash
psql -d postgres -c "CREATE ROLE microloan LOGIN PASSWORD '123' CREATEDB;"
```

(Use whatever superuser access your install has — `psql -d postgres` if your OS user is a
superuser, otherwise `sudo -u postgres psql`.)

Then, in two terminals:

```bash
# terminal 1 — backend
cd api
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend
cd web
npm install
npm run dev
```

**No `.env` needed.** The built-in defaults already point at
`postgresql+psycopg://microloan:123@localhost:5432/microloan`, and the frontend defaults to
`http://localhost:8000`.

**Starting the API creates the database, creates every table, and loads the demo data** —
there is no migrate step and no seed step to remember (ADR-018). The first boot says so:

```
INFO:     created database 'microloan'
INFO:     schema is at revision 0001
INFO:     seed: 3 staff logins · 20 members (1 INACTIVE) · 8 loans in every status …
INFO:     Application startup complete.
```

Restart it and every step finds nothing to do:

```
INFO:     schema is at revision 0001
INFO:     seed: 3 staff logins verified; portfolio already present
```

Each step can be switched off (`AUTO_CREATE_DATABASE`, `AUTO_MIGRATE`, `AUTO_SEED`) for an
environment that provisions its database elsewhere — see [DATABASE.md](DATABASE.md) §7.

The `microloan` database now sits in your normal server list, next to whatever else you have
there, and is browsable in pgAdmin or DBeaver on the usual port — see below.

### Under Docker Compose (the zero-install demo)

**Prerequisites:** Docker and Docker Compose, nothing else.

```bash
cp .env.example .env
docker compose up
```

Same bootstrap, same result — but this brings **its own Postgres**, published on **5433**
rather than 5432 so it cannot collide with the native server. Its data lives in a Docker
volume and is separate from the native database; nothing you do in one shows up in the other.

To run the apps natively but keep the database in a container, start only that service and
set `DATABASE_URL` to the 5433 port:

```bash
docker compose up -d postgres
DATABASE_URL=postgresql+psycopg://microloan:123@localhost:5433/microloan \
  .venv/bin/uvicorn app.main:app --reload --port 8000
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres (native) | `localhost:5432`, database `microloan` |
| Postgres (compose) | `localhost:5433`, database `microloan` |

### Testing the API from Swagger

Open **http://localhost:8000/docs**. Authentication needs no setup — the session is an
httpOnly cookie, and Swagger is served from the same origin as the API, so the browser
carries it for you:

1. **`POST /auth/login`** → *Try it out* → `{"email": "admin@demo.local", "password": "demo1234"}` → *Execute*.
2. Every protected endpoint now works. There is no token to copy and no **Authorize** button to press.
3. **Switch roles** by running `POST /auth/login` again with a different email — the new cookie replaces the old one. This is the quickest way to see the role checks fire:

   | As | Call | Expect |
   |---|---|---|
   | officer | `GET /audit-log` | `403 FORBIDDEN` — *requires role ADMIN; you are OFFICER* |
   | cashier | `POST /members` | `403 FORBIDDEN` — *requires role OFFICER or ADMIN* |
   | admin | `GET /audit-log` | `200` |

4. **`POST /auth/logout`** clears the cookie; `GET /auth/me` then returns `401`.

Note that `/docs` loads Swagger UI from a CDN, so it needs an internet connection. The raw
spec at `/openapi.json` does not.

### Demo logins

Created on startup, and repaired on every boot — an account deactivated or given the wrong
role during a demo comes back correct on the next restart.
**Demo credentials only — never use these anywhere real.**

| Role | Email | Password |
|---|---|---|
| Admin | `admin@demo.local` | `demo1234` |
| Officer | `officer@demo.local` | `demo1234` |
| Cashier | `cashier@demo.local` | `demo1234` |

New to the app? [DEMO.md](DEMO.md) is a scripted walkthrough — every feature, in the order
each role would meet it.

### Looking at the database in pgAdmin or DBeaver

`microloan` is an ordinary database on your local server, so it appears in the connection you
already use — alongside your other databases. No new connection needed if you have one:

| Host | Port | Database | User | Password |
|---|---|---|---|---|
| `localhost` | `5432` | `microloan` | `microloan` | `123` |

You can also browse it as your own superuser (`psql -d microloan`) rather than as the app's
role. If you are running the Compose stack instead, everything above is the same but on port
**5433** — a separate server with a separate copy of the data.

[DATABASE.md](DATABASE.md) §8 has the click-path for both tools and a short list of things
worth opening — the partial unique index that *is* the one-active-loan rule, and the triggers
that make the ledger append-only.

### Starting over

Drop the database and let the next boot rebuild it:

```bash
psql -d postgres -c "DROP DATABASE microloan WITH (FORCE);"
.venv/bin/uvicorn app.main:app --port 8000      # recreates, migrates, reseeds
```

Under Compose, drop the volume instead: `docker compose down -v && docker compose up`.

Either way the reset is a *clean* database. The demo portfolio is never re-applied on top of
itself — the ledger is append-only, so there is no delete-and-reinsert path, by design.

### Running the tests

```bash
cd api && pytest              # everything: domain + API integration
cd api && pytest tests/domain # the arithmetic alone — fast, no database
```

The API suite creates and migrates a throwaway `microloan_test` database once per session
on whatever `DATABASE_URL` points at — your native server by default — then builds its own
data through the API. It drops and recreates that database on every run and never touches
`microloan`.

The same suite runs inside the Compose stack, with no local Python at all:

```bash
docker compose exec api pytest
```

### Verifying the books balance

```bash
psql -d microloan -f api/scripts/check_invariants.sql
```

Every violations count must be `0`. Under Compose:
`docker compose exec -T postgres psql -U microloan -d microloan -f - < api/scripts/check_invariants.sql`

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
5. **`api/app/seeds.py`** — loans in every status, built through the real services, from
   fixed dates, so the demo looks the same every run.
6. **`api/app/bootstrap.py`** — the five idempotent steps between "container started" and
   "database ready", and why none of them is `create_all()`.

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
