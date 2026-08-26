"""Member registration and lookup — DOMAIN.md §11.

Members are never deleted, only deactivated. A member with an APPROVED or
DISBURSED loan cannot be deactivated.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import audit
from app.errors import duplicate_field, invalid_state, not_found
from app.models import Loan, LoanStatus, Member, MemberStatus, User
from app.services.helpers import next_code, outstanding_by_loan

_ACTIVE_LOAN_STATUSES = (LoanStatus.APPROVED, LoanStatus.DISBURSED)


def create(
    session: Session,
    *,
    full_name: str,
    phone: str,
    national_id: str,
    address: str | None,
    joined_on: date,
    actor: User,
) -> Member:
    # One service call = one transaction (ARCHITECTURE.md §3.2): reads, writes,
    # and the audit row all commit together at the end — or not at all.
    dup = session.scalar(
        select(Member).where(or_(Member.phone == phone, Member.national_id == national_id))
    )
    if dup is not None:
        field = "phone" if dup.phone == phone else "national ID"
        raise duplicate_field(f"A member with this {field} already exists ({dup.member_code}).")

    member = Member(
        member_code=next_code(session, Member.member_code, "M-"),
        full_name=full_name,
        phone=phone,
        national_id=national_id,
        address=address,
        joined_on=joined_on,
        status=MemberStatus.ACTIVE,
        created_by=actor.id,
    )
    session.add(member)
    session.flush()  # populate member.id before the audit row references it
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.MEMBER_CREATED,
        entity_type="member",
        entity_id=member.id,
        after={"member_code": member.member_code, "full_name": member.full_name},
    )
    session.commit()
    return member


def list_members(
    session: Session,
    *,
    q: str | None = None,
    status: MemberStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Member], int]:
    stmt = select(Member)
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            or_(
                Member.full_name.ilike(needle),
                Member.phone.ilike(needle),
                Member.member_code.ilike(needle),
            )
        )
    if status is not None:
        stmt = stmt.where(Member.status == status)

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    members = session.scalars(
        stmt.order_by(Member.member_code).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(members), total or 0


def func_count():
    from sqlalchemy import func

    return func.count()


def active_loan_map(session: Session, member_ids: list[uuid.UUID]) -> dict[uuid.UUID, Loan]:
    """The member's at-most-one active loan (R2 makes 'at most one' a guarantee)."""
    if not member_ids:
        return {}
    loans = session.scalars(
        select(Loan).where(Loan.member_id.in_(member_ids), Loan.status.in_(_ACTIVE_LOAN_STATUSES))
    ).all()
    return {loan.member_id: loan for loan in loans}


def get(session: Session, member_id: uuid.UUID) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("No member with this id.")
    return member


def detail(session: Session, member_id: uuid.UUID) -> tuple[Member, list[tuple[Loan, Decimal]]]:
    """The member plus every loan they have ever had, each with its outstanding."""
    member = get(session, member_id)
    loans = list(
        session.scalars(
            select(Loan)
            .where(Loan.member_id == member_id)
            .order_by(Loan.applied_on, Loan.loan_code)
        ).all()
    )
    outstanding = outstanding_by_loan(session, [loan.id for loan in loans])
    return member, [(loan, outstanding.get(loan.id, Decimal("0.00"))) for loan in loans]


def set_status(
    session: Session, *, member_id: uuid.UUID, status: MemberStatus, actor: User
) -> Member:
    member = get(session, member_id)
    if status == MemberStatus.INACTIVE:
        active = session.scalar(
            select(func.count()).where(
                Loan.member_id == member_id, Loan.status.in_(_ACTIVE_LOAN_STATUSES)
            )
        )
        if active:
            raise invalid_state(
                f"{member.member_code} has an active loan and cannot be deactivated."
            )

    before = {"status": member.status.value}
    member.status = status
    audit.record(
        session,
        actor_id=actor.id,
        action=audit.MEMBER_DEACTIVATED,
        entity_type="member",
        entity_id=member.id,
        before=before,
        after={"status": status.value},
    )
    session.commit()
    return member

