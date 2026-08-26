"""Member endpoints — thin: validate, resolve the user, delegate, serialise."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Member, MemberStatus, User, UserRole
from app.pagination import clamp
from app.schemas.common import Page
from app.schemas.members import (
    MemberCreate,
    MemberDetail,
    MemberListItem,
    MemberLoanSummary,
    MemberStatusIn,
)
from app.services import member_service
from app.services.helpers import outstanding_by_loan
from app.security import require_role

router = APIRouter(prefix="/members", tags=["members"])

ZERO = Decimal("0.00")


def _detail(session: Session, member: Member) -> MemberDetail:
    _, loans = member_service.detail(session, member.id)
    return MemberDetail(
        id=member.id,
        member_code=member.member_code,
        full_name=member.full_name,
        phone=member.phone,
        national_id=member.national_id,
        address=member.address,
        joined_on=member.joined_on,
        status=member.status,
        created_by=member.created_by,
        created_at=member.created_at,
        loans=[
            MemberLoanSummary(
                id=loan.id,
                loan_code=loan.loan_code,
                status=loan.status,
                principal=loan.principal,
                outstanding=outstanding,
            )
            for loan, outstanding in loans
        ],
    )


@router.get("", response_model=Page[MemberListItem])
def list_members(
    q: str | None = None,
    status: MemberStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    page, page_size = clamp(page, page_size)
    members, total = member_service.list_members(
        session, q=q, status=status, page=page, page_size=page_size
    )
    active = member_service.active_loan_map(session, [m.id for m in members])
    outstanding = outstanding_by_loan(session, [loan.id for loan in active.values()])
    items = [
        MemberListItem(
            id=m.id,
            member_code=m.member_code,
            full_name=m.full_name,
            phone=m.phone,
            status=m.status,
            active_loan_code=active[m.id].loan_code if m.id in active else None,
            outstanding=outstanding.get(active[m.id].id, ZERO) if m.id in active else ZERO,
        )
        for m in members
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=MemberDetail, status_code=201)
def create_member(
    body: MemberCreate,
    user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    member = member_service.create(
        session,
        full_name=body.full_name,
        phone=body.phone,
        national_id=body.national_id,
        address=body.address,
        joined_on=body.joined_on,
        actor=user,
    )
    return _detail(session, member)


@router.get("/{member_id}", response_model=MemberDetail)
def get_member(
    member_id: uuid.UUID,
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    return _detail(session, member_service.get(session, member_id))


@router.patch("/{member_id}/status", response_model=MemberDetail)
def set_member_status(
    member_id: uuid.UUID,
    body: MemberStatusIn,
    user: User = Depends(require_role(UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    member = member_service.set_status(
        session, member_id=member_id, status=body.status, actor=user
    )
    return _detail(session, member)
