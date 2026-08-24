# API — MicroLoan Demo

> FastAPI, JSON over HTTP. Interactive docs at `http://localhost:8000/docs` when running.
> Business rules referenced as **R1–R6** are defined in [DOMAIN.md](DOMAIN.md) §3.

---

## 1. Conventions

- Base URL `http://localhost:8000`. All request and response bodies are JSON.
- **Money** is sent and received as a **string** with 2 decimals (`"105538.46"`), never a
  JSON number — this avoids float rounding in JavaScript entirely.
- **Dates** are `YYYY-MM-DD`. Timestamps are ISO-8601 with timezone.
- Authentication is the `access_token` httpOnly cookie set by `POST /auth/login`.
- List endpoints accept `page` (default 1) and `page_size` (default 20, max 100) and return:
  ```json
  { "items": [ … ], "total": 137, "page": 1, "page_size": 20 }
  ```

### Error contract

Every error has the same shape, so the frontend has exactly one error path:

```json
{ "detail": { "code": "MEMBER_HAS_ACTIVE_LOAN",
              "message": "Member M-000042 already has an active loan (L-000019)." } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHENTICATED` | 401 | Missing, expired, or invalid token |
| `FORBIDDEN` | 403 | Authenticated, but the role is not permitted |
| `FORBIDDEN_SELF_APPROVAL` | 403 | **R1** — you created this loan, so you cannot approve it |
| `NOT_FOUND` | 404 | No such member / loan / repayment |
| `DUPLICATE_FIELD` | 409 | Phone, national ID, or email already exists |
| `MEMBER_HAS_ACTIVE_LOAN` | 409 | **R2** |
| `INVALID_STATE` | 409 | **R3** — the operation is not legal from this loan status |
| `INVALID_DATE` | 422 | **R5** — date ordering violated |
| `AMOUNT_EXCEEDS_OUTSTANDING` | 422 | **R6** — includes the settlement figure in `message` |
| `VALIDATION_ERROR` | 422 | Pydantic schema failure; includes field details |

---

## 2. Endpoint catalogue

| Method | Path | Role | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | public | Log in, receive the session cookie |
| `POST` | `/auth/logout` | any | Clear the cookie |
| `GET` | `/auth/me` | any | Current user and role |
| `GET` | `/members` | any | List and search members |
| `POST` | `/members` | OFFICER, ADMIN | Register a member |
| `GET` | `/members/{id}` | any | Member detail with loan history |
| `PATCH` | `/members/{id}/status` | ADMIN | Activate / deactivate |
| `POST` | `/loans/preview` | OFFICER, ADMIN | Calculate a schedule without saving anything |
| `POST` | `/loans` | OFFICER, ADMIN | Create a loan application |
| `GET` | `/loans` | any | List, filter, and search loans |
| `GET` | `/loans/{id}` | any | Loan detail: schedule, allocations, accrued fees |
| `POST` | `/loans/{id}/approve` | ADMIN | Approve (R1, R2) |
| `POST` | `/loans/{id}/reject` | ADMIN | Reject with a reason |
| `POST` | `/loans/{id}/disburse` | CASHIER, ADMIN | Release funds and generate the schedule |
| `GET` | `/loans/{id}/settlement-quote` | any | What it costs to close the loan today |
| `POST` | `/repayments` | CASHIER, ADMIN | Record a payment |
| `GET` | `/repayments` | any | List and search repayments |
| `GET` | `/repayments/{id}` | any | Receipt with its allocation breakdown |
| `GET` | `/dashboard/metrics` | any | The five headline numbers |
| `GET` | `/audit-log` | ADMIN | Who did what, when |
| `GET` | `/health` | public | Liveness probe |

---

## 3. Authentication

### `POST /auth/login`

```json
→ { "email": "admin@demo.local", "password": "demo1234" }

← 200  Set-Cookie: access_token=<jwt>; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800
  { "id": "…", "full_name": "Ayesha Rahman", "email": "admin@demo.local", "role": "ADMIN" }
```

JWT claims: `{"sub": <user_id>, "role": "ADMIN", "exp": …}`. Errors: `UNAUTHENTICATED` (401)
for a bad password or an inactive user — the message is identical in both cases so the
endpoint cannot be used to discover which emails exist.

### `GET /auth/me`
Returns the same user object. Used by the frontend shell to render role-aware navigation.

---

## 4. Members

### `POST /members` — OFFICER, ADMIN

```json
→ { "full_name": "Rahim Uddin", "phone": "01712345678",
    "national_id": "1990123456789", "address": "Mirpur, Dhaka",
    "joined_on": "2026-01-02" }

← 201
  { "id": "…", "member_code": "M-000042", "full_name": "Rahim Uddin",
    "phone": "01712345678", "national_id": "1990123456789",
    "address": "Mirpur, Dhaka", "joined_on": "2026-01-02",
    "status": "ACTIVE", "created_at": "2026-01-02T09:14:03+06:00" }
```

`member_code` is assigned by the server. Errors: `DUPLICATE_FIELD` (409) on phone or
national ID, `VALIDATION_ERROR` (422).

### `GET /members` — any

Query: `q` (matches name, phone, or member code), `status`, `page`, `page_size`.

```json
← { "items": [ { "id": "…", "member_code": "M-000042", "full_name": "Rahim Uddin",
                 "phone": "01712345678", "status": "ACTIVE",
                 "active_loan_code": "L-000019",
                 "outstanding": "79153.82" } ],
    "total": 137, "page": 1, "page_size": 20 }
```

### `GET /members/{id}` — any
Adds `address`, `joined_on`, `created_by`, and `loans[]` — every loan the member has ever
had, with status, principal, and outstanding.

### `PATCH /members/{id}/status` — ADMIN

```json
→ { "status": "INACTIVE" }
```

Errors: `INVALID_STATE` (409) if the member has an `APPROVED` or `DISBURSED` loan.

---

## 5. Loans

### `POST /loans/preview` — OFFICER, ADMIN

Pure calculation. **Writes nothing.** Lets the officer show the customer the numbers before
committing. Because `disbursed_on` is not known yet, pass a `start_date` to see indicative
due dates.

```json
→ { "principal": "100000.00", "interest_rate_annual": "12.00",
    "term_count": 24, "frequency": "WEEKLY", "start_date": "2026-01-05" }

← 200
  { "principal": "100000.00", "total_interest": "5538.46",
    "total_payable": "105538.46", "installment_amount": "4397.44",
    "schedule": [ { "seq": 1,  "due_date": "2026-01-12",
                    "principal_due": "4166.67", "interest_due": "230.77",
                    "amount_due": "4397.44" },
                  { "seq": 24, "due_date": "2026-06-22",
                    "principal_due": "4166.59", "interest_due": "230.75",
                    "amount_due": "4397.34" } ] }
```

### `POST /loans` — OFFICER, ADMIN

```json
→ { "member_id": "…", "principal": "100000.00", "interest_rate_annual": "12.00",
    "term_count": 24, "frequency": "WEEKLY",
    "late_fee": "100.00", "grace_days": 3, "applied_on": "2026-01-02" }

← 201  { "id": "…", "loan_code": "L-000019", "status": "PENDING", … }
```

Errors: `MEMBER_HAS_ACTIVE_LOAN` (409, R2), `INVALID_STATE` (409) if the member is
`INACTIVE`, `NOT_FOUND` (404).

### `GET /loans` — any
Query: `status`, `member_id`, `q` (loan code or member name/code), `page`, `page_size`.
Each item carries `loan_code`, member name and code, `principal`, `status`, `total_payable`,
`outstanding`, and `next_due_date`.

### `GET /loans/{id}` — any

Query: `as_of` (default: today) — controls fee calculation.

```json
← { "id": "…", "loan_code": "L-000019", "status": "DISBURSED",
    "member": { "id": "…", "member_code": "M-000042", "full_name": "Rahim Uddin" },
    "terms": { "principal": "100000.00", "interest_rate_annual": "12.00",
               "term_count": 24, "frequency": "WEEKLY",
               "late_fee": "100.00", "grace_days": 3 },
    "totals": { "total_interest": "5538.46", "total_payable": "105538.46",
                "installment_amount": "4397.44", "paid_total": "26384.64",
                "outstanding": "79153.82", "accrued_fees": "100.00" },
    "dates": { "applied_on": "2026-01-02", "approved_at": "2026-01-03T…",
               "disbursed_on": "2026-01-05", "closed_at": null },
    "people": { "created_by": "Karim (OFFICER)", "approved_by": "Ayesha (ADMIN)",
                "disbursed_by": "Nadia (CASHIER)" },
    "schedule": [ { "seq": 7, "due_date": "2026-02-23",
                    "principal_due": "4166.67", "interest_due": "230.77",
                    "amount_due": "4397.44",
                    "principal_paid": "0.00", "interest_paid": "0.00",
                    "fee_paid": "0.00",
                    "status": "PENDING", "accrued_fee": "100.00",
                    "allocations": [] } ] }
```

`status` and `accrued_fee` on a schedule row are **computed, not stored** — see
[DATABASE.md](DATABASE.md) §2.4 and [DOMAIN.md](DOMAIN.md) §8.

### `POST /loans/{id}/approve` — ADMIN

No request body. Errors: `FORBIDDEN_SELF_APPROVAL` (403, R1),
`MEMBER_HAS_ACTIVE_LOAN` (409, R2), `INVALID_STATE` (409) unless the loan is `PENDING`.

### `POST /loans/{id}/reject` — ADMIN

```json
→ { "reason": "Insufficient repayment capacity documented." }
```

### `POST /loans/{id}/disburse` — CASHIER, ADMIN

```json
→ { "disbursed_on": "2026-01-05" }

← 200  the full loan detail, now with all 24 installments
```

One transaction writes: loan status and frozen totals, N installment rows, one
`DISBURSEMENT` ledger entry, one audit row. Errors: `INVALID_STATE` (409) unless the loan is
`APPROVED`, `INVALID_DATE` (422, R5) if `disbursed_on < applied_on` or is in the future.

### `GET /loans/{id}/settlement-quote` — any

Query: `as_of` (default: today).

```json
← { "as_of": "2026-03-01", "outstanding": "79153.82",
    "accrued_fees": "100.00", "settlement_total": "79253.82" }
```

Flat interest means there is no rebate for settling early — see [DOMAIN.md](DOMAIN.md) §10.

---

## 6. Repayments

### `POST /repayments` — CASHIER, ADMIN

```json
→ { "loan_id": "…", "amount": "10000.00", "paid_on": "2026-01-20",
    "method": "CASH", "note": "Collected at Mirpur branch" }

← 201
  { "id": "…", "receipt_no": "R-000311", "loan_code": "L-000019",
    "member": { "member_code": "M-000042", "full_name": "Rahim Uddin" },
    "amount": "10000.00", "paid_on": "2026-01-20", "method": "CASH",
    "received_by": "Nadia (CASHIER)",
    "allocations": [
      { "seq": 1, "due_date": "2026-01-12", "fee": "0.00",
        "interest": "230.77", "principal": "4166.67", "total": "4397.44" },
      { "seq": 2, "due_date": "2026-01-19", "fee": "0.00",
        "interest": "230.77", "principal": "4166.67", "total": "4397.44" },
      { "seq": 3, "due_date": "2026-01-26", "fee": "0.00",
        "interest": "230.77", "principal": "974.35", "total": "1205.12" } ],
    "loan_status_after": "DISBURSED",
    "outstanding_after": "95538.46" }
```

The allocation breakdown is returned so the receipt printed for the customer shows exactly
where their money went. Errors:

- `INVALID_STATE` (409) — the loan is not `DISBURSED`
- `INVALID_DATE` (422, R5) — `paid_on` before `disbursed_on`, or in the future
- `AMOUNT_EXCEEDS_OUTSTANDING` (422, R6) — message contains the settlement figure

If the payment clears the final installment, `loan_status_after` is `CLOSED`.

**A repayment cannot be edited or deleted.** There is no `PATCH` or `DELETE` — the database
refuses it (see [DATABASE.md](DATABASE.md) §3.1). Correcting a mistake is a v1 non-goal.

### `GET /repayments` — any
Query: `receipt_no`, `loan_id`, `member_id`, `from`, `to`, `method`, `page`, `page_size`.

### `GET /repayments/{id}` — any
The full receipt with its allocations, as shown above.

---

## 7. Dashboard

### `GET /dashboard/metrics` — any

```json
← { "members_total": 137,
    "loans_active": 42,
    "disbursed_total": "4250000.00",
    "collected_total": "1187430.50",
    "outstanding_total": "3348219.62" }
```

The exact SQL behind each figure is in [DATABASE.md](DATABASE.md) §5. Note that
`disbursed_total − collected_total` is deliberately **not** equal to `outstanding_total`:
the first pair describes cash movement, the third describes the contractual balance on
active loans.

---

## 8. Audit log

### `GET /audit-log` — ADMIN only

Query: `entity_type`, `entity_id`, `actor_user_id`, `action`, `from`, `to`, `page`.

```json
← { "items": [ { "occurred_at": "2026-01-05T11:02:44+06:00",
                 "actor": "Nadia (CASHIER)", "action": "LOAN_DISBURSED",
                 "entity_type": "loan", "entity_id": "…",
                 "before": { "status": "APPROVED" },
                 "after":  { "status": "DISBURSED", "disbursed_on": "2026-01-05" } } ],
    "total": 1042, "page": 1, "page_size": 20 }
```

Every state change in the system produces one of these rows, written in the same transaction
as the change itself.
