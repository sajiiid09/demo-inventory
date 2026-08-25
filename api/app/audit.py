"""The audit trail — every state change, written inside the SAME transaction
as the change it records (DATABASE.md §2.8). If the change rolls back, so does
the audit row; if the audit row fails, so does the change.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

# Canonical action names (DATABASE.md §2.8) — reuse these, never invent strings.
MEMBER_CREATED = "MEMBER_CREATED"
MEMBER_DEACTIVATED = "MEMBER_DEACTIVATED"
LOAN_CREATED = "LOAN_CREATED"
LOAN_APPROVED = "LOAN_APPROVED"
LOAN_REJECTED = "LOAN_REJECTED"
LOAN_DISBURSED = "LOAN_DISBURSED"
REPAYMENT_RECORDED = "REPAYMENT_RECORDED"
LOAN_CLOSED = "LOAN_CLOSED"
USER_LOGGED_IN = "USER_LOGGED_IN"


def record(
    session: Session,
    *,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
