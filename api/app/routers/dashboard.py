"""Dashboard and audit-log endpoints."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AuditLog, User, UserRole
from app.pagination import clamp
from app.schemas.audit import AuditLogItem
from app.schemas.common import Page
from app.schemas.dashboard import DashboardMetrics
from app.security import require_role
from app.services import dashboard_service

router = APIRouter(tags=["dashboard & audit"])


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    user: User = Depends(require_role()),
    session: Session = Depends(get_session),
):
    return dashboard_service.metrics(session)


@router.get("/audit-log", response_model=Page[AuditLogItem])
def audit_log(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(UserRole.ADMIN)),
    session: Session = Depends(get_session),
):
    page, page_size = clamp(page, page_size)
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AuditLog.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.occurred_at < date_to + dt.timedelta(days=1))

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(AuditLog.occurred_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        AuditLogItem(
            occurred_at=row.occurred_at,
            actor=f"{row.actor.full_name} ({row.actor.role.value})",
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before=row.before,
            after=row.after,
        )
        for row in rows
    ]
    return Page(items=items, total=total or 0, page=page, page_size=page_size)
