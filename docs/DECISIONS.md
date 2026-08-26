# Decision Log (ADRs) — MicroLoan Demo

> One record per decision: what was chosen, why, what was rejected, and what it costs.
> A decision without a recorded alternative is a habit, not a decision.
> Status of every ADR below: **Accepted**, 2026-08-24, before implementation began.

| # | Decision |
|---|---|
| [001](#adr-001) | FastAPI + SQLAlchemy 2.0 + Alembic, not Prisma |
| [002](#adr-002) | Flat interest, not reducing-balance EMI |
| [003](#adr-003) | The schedule is persisted at disbursement, not at approval |
| [004](#adr-004) | Late fees are computed on read, not accrued by a job |
| [005](#adr-005) | One active loan per member, enforced by a partial unique index |
| [006](#adr-006) | An append-only ledger, protected by database triggers |
| [007](#adr-007) | JWT in an httpOnly cookie, not in localStorage |
| [008](#adr-008) | `NUMERIC(14,2)` and `Decimal`, never `float` |
| [009](#adr-009) | Three roles with real separation of duties |
| [010](#adr-010) | One repository containing `api/` and `web/` |
| [011](#adr-011) | Pure domain layer with no clock and no database |
| [012](#adr-012) | Payment reversal is out of scope for v1 |
| [013](#adr-013) | A flat late fee per overdue installment, not a daily percentage |
| [014](#adr-014) | Exactly the five dashboard metrics from the brief, all-time |
| [015](#adr-015) | Weekly and monthly frequencies only |
| [016](#adr-016) | Core identity only on a member record |
| [017](#adr-017) | A server-rendered Next.js UI, plainly styled |

---

## ADR-001 — FastAPI + SQLAlchemy 2.0 + Alembic, not Prisma {#adr-001}

**Context.** A Python backend was wanted for the learning value and because the larger
project ahead is likely to be Python. Prisma was the initial preference for its readable
schema file and its migration workflow.

**Decision.** Python 3.12 + FastAPI + SQLAlchemy 2.0 (typed `Mapped[]` declarative models) +
Alembic.

**Rejected — Prisma with Python.** Prisma is a TypeScript ORM. Its Python client is a
third-party port that has been effectively unmaintained since 2024, with known friction
around Pydantic v2 and modern Python versions. Shipping a trial project on an unmaintained
data layer is not defensible in a review.

**Rejected — switching the backend to Node so Prisma fits.** Would have kept Prisma and made
the whole stack TypeScript, but discards the Python learning goal that motivated the choice.

**Rejected — SQLModel.** Less boilerplate and closer in feel to Prisma, but thinner escape
hatches for the more involved queries (the dashboard aggregates, `SELECT … FOR UPDATE`) and
a smaller community.

**Consequences.** SQLAlchemy 2.0's typed models give a single readable `models/` package
that reads much like a Prisma schema. Alembic revisions are real, reviewable Python/SQL
files. The cost is more explicit session and transaction handling — which is arguably a
benefit here, since the transaction boundary is something we want to be visible.

---

## ADR-002 — Flat interest, not reducing-balance EMI {#adr-002}

**Context.** The interest method determines the schedule, the repayment logic, the early
settlement rules, and how hard the whole system is to explain.

**Decision.** Flat interest: `interest = principal × annual_rate × (term / periods_per_year)`,
computed once and frozen at disbursement.

**Rejected — reducing balance (EMI).** More realistic for bank lending and the standard for
commercial products, but the amortisation formula cannot be verified by hand in a meeting,
and each installment's principal/interest split changes every period.

**Rejected — both, selectable per loan.** Maximum flexibility and a nicer architecture story,
but it doubles the schedule logic and the test surface for a trial demo that will only ever
be shown with one method.

**Consequences.** The arithmetic is verifiable on paper in seconds (see
[DOMAIN.md](../DOMAIN.md) §6), which is exactly what a demo needs. It matches common
microfinance and NGO lending practice in South Asia. The cost: **there is no interest rebate
for early settlement** — a flat loan's total payable never shrinks. This is the most likely
question in a review, and the honest answer is that it is a property of the product, not a
bug. Adding reducing-balance later means one new branch in `schedule.py`; the pure domain
layer keeps that change contained.

---

## ADR-003 — The schedule is persisted at disbursement, not at approval {#adr-003}

**Context.** Installment rows have to be created at some point in the loan lifecycle. Due
dates depend on a start date.

**Decision.** The schedule is *previewed* at application time as a pure calculation that
writes nothing, and *persisted* at disbursement, anchored to the real `disbursed_on` date.

**Rejected — persist at approval.** The approval date is not the funding date. If money goes
out three days later, every due date has to be shifted with an update sweep, which muddies
both the ledger and the audit trail.

**Rejected — persist at application.** Simplest mental model, but it writes a schedule for
loans that may be rejected and never funded, leaving orphan rows that every query has to
filter around.

**Consequences.** Due dates always reflect reality. Approval is a cheap status change.
Disbursement becomes the one interesting transaction in the system — status, frozen totals,
N installment rows, a ledger entry, and an audit row, all or nothing. `POST /loans/preview`
gives the officer the numbers to show the customer without any write at all.

---

## ADR-004 — Late fees are computed on read, not accrued by a job {#adr-004}

**Context.** Overdue installments attract a flat late fee. Something has to decide when that
fee exists.

**Decision.** `penalty_due(installment, late_fee, grace_days, as_of)` is a pure function
evaluated whenever a loan is read. A fee becomes a database row only at the moment a payment
allocates money to it.

**Rejected — a nightly scheduled job writing fee rows.** More "production-like" and the fee
is visible in the database immediately, but it introduces a scheduler that must be running
for the demo to look right, idempotency questions if it runs twice, and gaps if it does not
run at all.

**Rejected — a cashier charging fees manually.** Perfect audit trail and zero automation, but
it fails the brief's requirement that the system calculate automatically.

**Consequences.** No background infrastructure. The fee owed on any past date can be
recomputed exactly, forever — useful for both testing and auditing. The trade-off: you cannot
`SELECT` total accrued fees across the portfolio in one query, since they are not stored.
Accepted, because fees are not a receivable until charged, and the dashboard's
`outstanding_total` deliberately excludes them.

---

## ADR-005 — One active loan per member, enforced by a partial unique index {#adr-005}

**Context.** Whether a member may hold several loans at once is a business rule, and the
brief does not say.

**Decision.** A member may hold at most one loan in `APPROVED` or `DISBURSED`. The rule lives
in the database:

```sql
CREATE UNIQUE INDEX one_active_loan_per_member
    ON loans (member_id)
    WHERE status IN ('APPROVED', 'DISBURSED');
```

**Rejected — multiple concurrent loans.** More realistic for a mature MFI and gives each
member a richer portfolio page, but eligibility becomes a service-layer rule with no
database-level guarantee, and "the member's outstanding balance" stops being a single number.

**Rejected — many loans but only one pending application.** A reasonable middle ground, but
two rules to explain instead of one.

**Consequences.** The invariant holds even if someone writes to the database directly.
Application code enforces it too — but only so the user gets `409 MEMBER_HAS_ACTIVE_LOAN`
instead of a raw integrity error. One honest wrinkle, documented in
[DATABASE.md](../DATABASE.md) §3.2: two `PENDING` applications can coexist, since an
application is only a request; approving the second is what gets refused.

---

## ADR-006 — An append-only ledger, protected by database triggers {#adr-006}

**Context.** "Database transparency" was a stated goal. The system must be able to show, for
any amount, where it came from and where it went.

**Decision.** `repayments`, `repayment_allocations`, `ledger_entries` and `audit_log` are
append-only. A `BEFORE UPDATE OR DELETE` trigger on each raises an exception. Every payment
is broken down into `repayment_allocations` rows that name the exact installment and the
split between fee, interest, and principal.

**Rejected — application-level convention only.** "We just never update those tables" is a
promise, not a guarantee, and it does not survive a developer with a psql prompt.

**Rejected — event sourcing the whole domain.** Total auditability, wildly disproportionate
for a trial demo, and hard to explain in a short meeting.

**Consequences.** Any balance can be reconstructed from the ledger; nothing can be quietly
rewritten. The cost is that correcting a mistaken entry needs a reversing entry rather than
an edit — see ADR-012.

---

## ADR-007 — JWT in an httpOnly cookie, not in localStorage {#adr-007}

**Context.** A Next.js browser client has to authenticate against a FastAPI backend, and
Server Components must be able to read data on the server.

**Decision.** `POST /auth/login` sets a signed JWT as an `HttpOnly; SameSite=Lax` cookie with
an 8-hour lifetime. `web/middleware.ts` verifies it for route gating; FastAPI re-verifies on
every request and is the sole authority on permissions.

**Rejected — a bearer token in localStorage.** The textbook approach and convenient in
Swagger, but the token sits in JavaScript-reachable storage, so a single XSS bug becomes a
session theft. It is also awkward with Server Components, which cannot read `localStorage`.

**Rejected — opaque session tokens in a `sessions` table.** Maximally transparent (you can
`SELECT` the live logins) and instantly revocable, at the cost of a database round-trip on
every request and another table. Worth revisiting for the production system, where
revocation matters.

**Consequences.** No client-side token handling anywhere. Server Components simply forward
the cookie. The trade-off is that a JWT cannot be revoked before it expires — acceptable at
an 8-hour lifetime for a demo, and the reason the alternative is written down here.

---

## ADR-008 — `NUMERIC(14,2)` and `Decimal`, never `float` {#adr-008}

**Context.** This system's entire purpose is arithmetic on money.

**Decision.** Postgres `NUMERIC(14,2)` ↔ Python `Decimal` end to end. Rounding is explicitly
`ROUND_HALF_UP` to two decimal places. The final installment absorbs the remainder so a
schedule sums to the exact total payable. Money crosses the API as a **string**, so
JavaScript never parses it into a float.

**Rejected — integer minor units (paisa) in `BIGINT`.** Bulletproof against any decimal
representation issue, but every read and write needs a ÷100 conversion, and the raw tables
become unreadable to a non-engineer inspecting them — which works against the transparency
goal.

**Rejected — `float` / `double precision`.** Never acceptable for money.

**Consequences.** `SUM(installments.amount_due) = loans.total_payable` holds exactly, and it
is asserted as a test invariant. `NUMERIC(14,2)` allows amounts up to 999,999,999,999.99 —
far beyond anything this system will see.

---

## ADR-009 — Three roles with real separation of duties {#adr-009}

**Context.** The brief asks only for "role-based" login. The number and shape of the roles is
ours to choose.

**Decision.** `OFFICER` registers members and creates applications; `ADMIN` approves and
rejects; `CASHIER` disburses and collects. Every role can read. One rule cuts across all of
them: **the person who created a loan may never approve it**, ADMIN included.

**Rejected — ADMIN + OFFICER only.** Simplest possible RBAC, but the same person then
approves and disburses, so the approval step demonstrates nothing.

**Rejected — adding a read-only AUDITOR role.** Pairs nicely with the audit log, but it is a
fourth seeded user and a fourth column in every permission table for a capability the other
three roles already have.

**Consequences.** The demo can show a real control failing: an OFFICER attempting to approve
their own loan is refused. That single moment communicates more about the system's design
than any diagram. The cost is three seeded users to keep straight during the demo.

---

## ADR-010 — One repository containing `api/` and `web/` {#adr-010}

**Context.** Two applications, one project, one demonstration.

**Decision.** A single git repository: `api/` (FastAPI), `web/` (Next.js), and a root
`docker-compose.yml` that starts Postgres, the API, and the web app together.

**Rejected — two repositories.** Closer to how a large team would version independent
services, but it means two clones, two setups, and a demo that starts with an apology.

**Rejected — a flat layout with everything at the root.** Fewest paths to explain, but
`pyproject.toml`, `package.json`, `.venv/` and `node_modules/` collide in one directory.

**Consequences.** `git clone` then `docker compose up`. The two applications stay cleanly
separated by directory, so extracting one into its own repository later is a `git filter`
away — a real possibility for the larger project.

---

## ADR-011 — Pure domain layer with no clock and no database {#adr-011}

**Context.** The correctness risk in a lending system is arithmetic, not CRUD. Arithmetic
bugs are invisible in a demo and expensive later.

**Decision.** Everything in `api/app/domain/` is a pure function. No SQLAlchemy import, no
I/O, and — critically — **no `date.today()`**. The current date is always passed in as an
explicit `as_of` argument.

**Rejected — calculation methods on the SQLAlchemy models.** Convenient (`loan.outstanding`)
and a common pattern, but it makes every arithmetic test require a database session, and it
tangles the schedule rules with persistence concerns.

**Rejected — calculation inline in the service functions.** Fewer files, but the rules end up
interleaved with transaction handling and cannot be tested without a database.

**Consequences.** The whole test suite for the arithmetic runs in under a second with no
infrastructure. Any question of the form "what did this loan owe on 1 March?" has a
deterministic answer. Every number the UI shows can be reproduced by hand from
[DOMAIN.md](../DOMAIN.md). The cost is a slightly longer call chain — the service loads rows,
converts them to plain values, calls the domain function, and applies the result. That
explicitness is the point.

---

## ADR-012 — Payment reversal is out of scope for v1 {#adr-012}

**Context.** Cashiers make mistakes: a wrong amount, a wrong loan, a duplicate receipt.

**Decision.** v1 has no way to void or edit a repayment. The database physically refuses it
(ADR-006).

**Rejected — an admin "void payment" action writing a reversing entry.** The correct
long-term design and consistent with the append-only ledger, but it adds a second entry type,
a reason field, sign handling throughout the allocation logic, and its own test matrix — for
a path that will not be exercised in a demo.

**Rejected — allowing an edit or a delete.** Would defeat the ledger guarantee that ADR-006
exists to provide.

**Consequences.** A mis-keyed payment in the demo cannot be undone; reseed the database
instead. This is a **known, deliberate limitation, not an oversight** — say so if it comes
up. When it is implemented, it will be a reversing `repayments` row with a negative-direction
ledger entry and a link to the receipt it corrects, never a mutation of the original.

---

## ADR-013 — A flat late fee per overdue installment, not a daily percentage {#adr-013}

**Context.** Overdue installments need a penalty. The shape of that penalty determines how
predictable the numbers are.

**Decision.** One fixed fee per overdue installment, charged once after a grace period, both
configured per loan (`late_fee`, `grace_days`). It never compounds and never grows with time.

**Rejected — a daily percentage of the overdue amount** (e.g. 0.05% per day). More realistic
and it does grow with delinquency, but the figure changes every single day, which makes
screenshots, documentation, and tests fragile, and makes the number harder to check by hand.

**Rejected — a one-off percentage of the installment.** Scales with loan size while staying a
fixed number — a reasonable middle ground, but it is a multiplication nobody can do in their
head, and the demo gains nothing from it.

**Consequences.** "Three days late or three hundred, it's 100 taka once" is a sentence anyone
can follow, and the boundary cases in [DOMAIN.md](../DOMAIN.md) §8 are a five-row table. The
fee is stored per loan rather than globally, so a future loan product can behave differently
without a schema change. Interest-on-arrears is not modelled at all.

---

## ADR-014 — Exactly the five dashboard metrics from the brief, all-time {#adr-014}

**Context.** The brief names five metrics. Dashboards attract additions.

**Decision.** Total members, active loans, total disbursed, total collections, total
outstanding. All-time, no date filter. Each is exactly one SQL query, written out verbatim in
[DATABASE.md](../DATABASE.md) §5.

**Rejected — adding overdue and portfolio-at-risk metrics.** They would exercise the late-fee
logic and look sharp in a demo, but they need a definition of "at risk" that the brief does
not give, and an undefined metric on a dashboard is worse than a missing one.

**Rejected — a date-range filter on every figure.** Realistic reporting, but every aggregate
then needs date-boundary care, and the counts and the sums answer the question differently
(a count is live, a sum is periodic).

**Consequences.** Every number on the dashboard can be reproduced in psql in front of the
person asking. Two behaviours are documented rather than smoothed over: `outstanding_total`
excludes accrued late fees, and `disbursed_total − collected_total` is deliberately not equal
to `outstanding_total`, because cash movement and contractual balance are different questions.

---

## ADR-015 — Weekly and monthly frequencies only {#adr-015}

**Context.** Term is expressed as a number of installments plus a frequency.

**Decision.** `WEEKLY` (52 periods per year) and `MONTHLY` (12). One enum, one date-stepping
function.

**Rejected — monthly only.** The least code, but weekly collection is the norm in
microfinance, so a demo without it misses the domain it is imitating.

**Rejected — adding daily.** Full flexibility, but daily schedules multiply the date edge
cases for a scheme this demo would never show.

**Consequences.** Weekly is trivial (`+ n × 7 days`). Monthly carries the one genuinely
fiddly rule in the system — clamping to the end of a short month, so a loan disbursed on
31 January falls due on 28 February and then 31 March, clamping from the original day each
time rather than drifting. That rule has its own tests.

---

## ADR-016 — Core identity only on a member record {#adr-016}

**Context.** Real microfinance registration forms are long. The demo does not need to be.

**Decision.** `member_code`, full name, phone (unique), national ID (unique), address, join
date, status, and who registered them.

**Rejected — adding nominee and guarantor details.** Standard on real forms and a realistic
touch, but four more fields or another table that no other part of the system reads.

**Rejected — adding photo and document upload.** Pulls in file storage, serving, and size
limits — none of which have anything to do with the loan engine this trial is meant to prove.

**Consequences.** Registration is one short form. The unique constraints on phone and
national ID give a clean, demonstrable duplicate-detection story. Members are never deleted,
only deactivated, so history stays intact.

---

## ADR-017 — A server-rendered Next.js UI, plainly styled {#adr-017}

**Context.** The brief asks for a dashboard, lists, search, and detail views. How much design
effort they deserve is a choice.

**Decision.** Next.js App Router with Server Components for reads, Server Actions for
writes, and plain Tailwind for a clean default look. **As built (amended during
implementation):** no shadcn/ui, and a deliberately thin page set — login, members
list + register, loans list + new with live preview, loan detail with role-gated
actions, and the dashboard. Member detail, repayments browsing/receipts, and the
audit-log UI are API-only (Swagger covers them).

**Rejected — adding charts to the dashboard.** More impressive on screen, but a chart library
and a trend query in exchange for information the five numbers already carry.

**Rejected — shadcn/ui primitives.** Attractive defaults and fast assembly, but a component
library's conventions are one more thing to explain, and this demo's frontend exists only
to prove the engine is clickable. Plain Tailwind tables, forms, and cards are fully legible
as code.

**Rejected — an unstyled, minimal UI.** Would concentrate all the effort on the backend, but
the person being shown this needs to click through a flow that looks finished.

**Consequences.** The UI stays legible as code, which matters because the point of the demo
is the domain logic underneath it. Every network call goes through one typed wrapper
(`web/lib/api.ts`), so the base URL, cookie forwarding, and error handling each exist in
exactly one place, and every write goes through one server-actions module with a single
error path. No frontend tests — recorded as a non-goal in
[ARCHITECTURE.md](../ARCHITECTURE.md) §8, and the reason the API suite covers the rules
directly.
