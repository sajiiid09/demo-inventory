"""Seed the demo database — fixed dates, identical every run.

Everything is built THROUGH THE SERVICES (not raw inserts), so the seed data
satisfies every rule and invariant by construction: schedules sum exactly,
allocations match payments, the ledger balances, and every step carries an
audit row.

Loan states covered: PENDING (×2 for one member — they may coexist, ADR-005),
APPROVED, REJECTED, DISBURSED unpaid, DISBURSED partly paid (the DOMAIN.md §9
case), DISBURSED overdue past grace, and CLOSED.

Run only on a fresh schema — the ledger is append-only, so reseeding means:
    alembic downgrade base && alembic upgrade head && python seed.py
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Member, MemberStatus, PaymentMethod, User, UserRole
from app.security import hash_password
from app.services import (
    loan_service,
    member_service,
    repayment_service,
)

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("admin@demo.local", "Ayesha Rahman", UserRole.ADMIN),
    ("officer@demo.local", "Karim Hussain", UserRole.OFFICER),
    ("cashier@demo.local", "Nadia Islam", UserRole.CASHIER),
]

D = Decimal

MEMBER_NAMES = [
    "Rahim Uddin",        # M-000001 — canonical weekly loan, partly paid (§9)
    "Sultana Begum",      # M-000002 — two PENDING applications
    "Jahanara Imam",      # M-000003 — APPROVED
    "Abdul Karim",        # M-000004 — REJECTED
    "Mizanur Rahman",     # M-000005 — DISBURSED, no payments
    "Shirin Akter",       # M-000006 — DISBURSED, overdue past grace
    "Kamal Hossain",      # M-000007 — CLOSED (settled in full)
    "Nasrin Sultana",     # M-000008 — no loans, will be INACTIVE
    "Farid Alam",
    "Ruma Khatun",
    "Shahin Miah",
    "Tanvir Ahmed",
    "Bilkis Banu",
    "Rafiqul Islam",
    "Salma Begum",
    "Jamal Uddin",
    "Rehana Parvin",
    "Anwar Hossain",
    "Momtaz Khatun",
    "Habibur Rahman",
]


def seed() -> None:
    with SessionLocal() as session:
        if session.scalar(select(Member).limit(1)) is not None:
            raise SystemExit(
                "Database already has members. To reseed from scratch:\n"
                "  alembic downgrade base && alembic upgrade head && python seed.py"
            )

        users = {}
        for email, full_name, role in DEMO_USERS:
            user = User(
                email=email, full_name=full_name, role=role,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            session.add(user)
        session.commit()
        for email, _, role in DEMO_USERS:
            users[role.value.lower()] = session.scalar(
                select(User).where(User.email == email)
            )
        officer, admin, cashier = users["officer"], users["admin"], users["cashier"]

        members = []
        for i, name in enumerate(MEMBER_NAMES, start=1):
            member = member_service.create(
                session,
                full_name=name,
                phone=f"017{89999999 - i:08d}",
                national_id=f"199{i:03d}000{i:04d}",
                address="Dhaka" if i % 2 else "Chattogram",
                joined_on=dt.date(2026, 1, 2) + dt.timedelta(days=i),
                actor=officer,
            )
            members.append(member)

        def apply(member, principal, rate, term, freq, **kw):
            return loan_service.create(
                session,
                member_id=member.id,
                principal=D(principal),
                interest_rate_annual=D(rate),
                term_count=term,
                frequency=freq,
                late_fee=D(kw.get("late_fee", "100.00")),
                grace_days=kw.get("grace_days", 3),
                applied_on=kw.get("applied_on", dt.date(2026, 1, 2)),
                actor=kw.get("by", officer),
            )

        # --- PENDING ×2 for one member (applications may coexist — ADR-005) ---
        apply(members[1], "40000.00", "12.00", 16, "WEEKLY", applied_on=dt.date(2026, 3, 1))
        apply(members[1], "25000.00", "10.00", 12, "WEEKLY", applied_on=dt.date(2026, 3, 4))

        # --- APPROVED ---
        approved = apply(
            members[2], "60000.00", "12.00", 12, "MONTHLY",
            applied_on=dt.date(2026, 3, 1),
        )
        loan_service.approve(session, loan_id=approved.id, actor=admin)

        # --- REJECTED ---
        rejected = apply(members[3], "90000.00", "15.00", 24, "WEEKLY",
                         applied_on=dt.date(2026, 2, 10))
        loan_service.reject(
            session, loan_id=rejected.id,
            reason="Insufficient repayment capacity documented.", actor=admin,
        )

        # --- DISBURSED, no payments (the canonical example A terms) ---
        unpaid = apply(members[4], "100000.00", "12.00", 24, "WEEKLY",
                       applied_on=dt.date(2026, 1, 2))
        loan_service.approve(session, loan_id=unpaid.id, actor=admin)
        loan_service.disburse(
            session, loan_id=unpaid.id, disbursed_on=dt.date(2026, 1, 5), actor=cashier
        )

        # --- DISBURSED, partly paid — DOMAIN.md §9 word for word ---
        partial = apply(members[0], "100000.00", "12.00", 24, "WEEKLY",
                        applied_on=dt.date(2026, 1, 2))
        loan_service.approve(session, loan_id=partial.id, actor=admin)
        loan_service.disburse(
            session, loan_id=partial.id, disbursed_on=dt.date(2026, 1, 5), actor=cashier
        )
        repayment_service.record(
            session, loan_id=partial.id, amount=D("10000.00"),
            paid_on=dt.date(2026, 1, 13), method=PaymentMethod.CASH,
            note="Collected at Mirpur branch", actor=cashier,
        )

        # --- DISBURSED, overdue past grace (accrued fees visible on detail) ---
        overdue = apply(members[5], "30000.00", "15.00", 12, "WEEKLY",
                        applied_on=dt.date(2026, 3, 5))
        loan_service.approve(session, loan_id=overdue.id, actor=admin)
        loan_service.disburse(
            session, loan_id=overdue.id, disbursed_on=dt.date(2026, 3, 10), actor=cashier
        )

        # --- CLOSED — small loan settled in one payment, no late fee product ---
        closing = apply(members[6], "20000.00", "10.00", 8, "WEEKLY",
                        late_fee="0.00", applied_on=dt.date(2026, 1, 20))
        loan_service.approve(session, loan_id=closing.id, actor=admin)
        loan_service.disburse(
            session, loan_id=closing.id, disbursed_on=dt.date(2026, 2, 2), actor=cashier
        )
        # 20,000 × 10% × 8/52 = 307.69 → total 20,307.69, settled in full
        repayment_service.record(
            session, loan_id=closing.id, amount=D("20307.69"),
            paid_on=dt.date(2026, 4, 1), method=PaymentMethod.BANK,
            note="Early settlement — flat interest, no rebate (DOMAIN.md §10)",
            actor=cashier,
        )

        # --- a member with no loans, deactivated ---
        member_service.set_status(
            session, member_id=members[7].id, status=MemberStatus.INACTIVE, actor=admin
        )

    print(
        "Seeded: 3 users · 20 members (1 INACTIVE) · 8 loans in every status "
        "(2 PENDING, 1 APPROVED, 1 REJECTED, 3 DISBURSED, 1 CLOSED) · 2 repayments."
    )


if __name__ == "__main__":
    seed()
