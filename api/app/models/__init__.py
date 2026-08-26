"""The whole database schema in one readable file.

Shape only — no behaviour, no computed business values. Those live in app/domain/
(ADR-011). Every table, column, and constraint here mirrors DATABASE.md §2–3.

Money rule (ADR-008): every money column is NUMERIC(14,2) ↔ Python Decimal.
Never float, anywhere, at any layer.

Append-only note: repayments, repayment_allocations, ledger_entries and audit_log
are protected by BEFORE UPDATE OR DELETE triggers (created in alembic revision
0001_init — triggers are not expressible as model declarations).
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Store the plain word ('ADMIN'), not the attribute name, in Postgres."""
    return [member.value for member in enum_cls]


# ---------------------------------------------------------------------------
# Enum types (native PostgreSQL enums, created by alembic revision 0001)
# ---------------------------------------------------------------------------


class UserRole(enum.Enum):
    ADMIN = "ADMIN"
    OFFICER = "OFFICER"
    CASHIER = "CASHIER"


class MemberStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class LoanStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISBURSED = "DISBURSED"
    CLOSED = "CLOSED"


class LoanFrequency(enum.Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class PaymentMethod(enum.Enum):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE = "MOBILE"


class LedgerEntryType(enum.Enum):
    DISBURSEMENT = "DISBURSEMENT"
    REPAYMENT = "REPAYMENT"


class LedgerDirection(enum.Enum):
    OUT = "OUT"
    IN = "IN"


# ---------------------------------------------------------------------------
# 2.1 users — staff accounts, seeded or created by an ADMIN; no self-registration
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=_enum_values)
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.2 members — never deleted, only deactivated
# ---------------------------------------------------------------------------


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    member_code: Mapped[str] = mapped_column(Text, unique=True)  # M-000001, sequential
    full_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text, unique=True)
    national_id: Mapped[str] = mapped_column(Text, unique=True)
    address: Mapped[str | None] = mapped_column(Text)
    joined_on: Mapped[date] = mapped_column(Date)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status", values_callable=_enum_values),
        default=MemberStatus.ACTIVE,
        server_default=text("'ACTIVE'"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loans: Mapped[list["Loan"]] = relationship(back_populates="member")


# ---------------------------------------------------------------------------
# 2.3 loans — terms freeze at disbursement (R4); one active loan per member (R2)
# ---------------------------------------------------------------------------


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("principal > 0", name="loans_principal_positive"),
        CheckConstraint("term_count > 0", name="loans_term_positive"),
        CheckConstraint("interest_rate_annual >= 0", name="loans_rate_non_negative"),
        CheckConstraint(
            "status <> 'REJECTED' OR rejection_reason IS NOT NULL",
            name="loans_rejection_has_reason",
        ),
        CheckConstraint(
            "status NOT IN ('DISBURSED', 'CLOSED') "
            "OR (disbursed_on IS NOT NULL AND total_payable IS NOT NULL)",
            name="loans_disbursed_has_terms",
        ),
        CheckConstraint(
            "disbursed_on IS NULL OR disbursed_on >= applied_on",
            name="loans_disbursed_after_applied",  # R5
        ),
        # R2: one active loan per member — enforced by Postgres, not by Python.
        Index(
            "one_active_loan_per_member",
            "member_id",
            unique=True,
            postgresql_where=text("status IN ('APPROVED', 'DISBURSED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    loan_code: Mapped[str] = mapped_column(Text, unique=True)  # L-000001
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), index=True
    )
    principal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    interest_rate_annual: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # percent/yr, flat
    term_count: Mapped[int] = mapped_column(Integer)
    frequency: Mapped[LoanFrequency] = mapped_column(
        Enum(LoanFrequency, name="loan_frequency", values_callable=_enum_values)
    )
    late_fee: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    grace_days: Mapped[int] = mapped_column(
        Integer, default=3, server_default=text("3")
    )
    # Frozen at disbursement (R4), NULL until then:
    total_interest: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_payable: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    installment_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, name="loan_status", values_callable=_enum_values),
        default=LoanStatus.PENDING,
        server_default=text("'PENDING'"),
        index=True,
    )
    applied_on: Mapped[date] = mapped_column(Date)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))  # R1 anchor
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    disbursed_on: Mapped[date | None] = mapped_column(Date)
    disbursed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    member: Mapped[Member] = relationship(back_populates="loans")
    creator: Mapped[User] = relationship(
        foreign_keys=[created_by], lazy="joined"
    )
    approver: Mapped[User | None] = relationship(
        foreign_keys=[approved_by], lazy="joined"
    )
    disbursor: Mapped[User | None] = relationship(
        foreign_keys=[disbursed_by], lazy="joined"
    )
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="loan",
        order_by="Installment.seq",
        cascade="save-update, merge",  # deliberately NOT delete-orphan: append-only world
    )
    repayments: Mapped[list["Repayment"]] = relationship(back_populates="loan")


# ---------------------------------------------------------------------------
# 2.4 installments — rows exist only for DISBURSED/CLOSED loans.
# Status (PENDING/PARTIAL/PAID) is derived, never stored.
# ---------------------------------------------------------------------------


class Installment(Base):
    __tablename__ = "installments"
    __table_args__ = (
        UniqueConstraint("loan_id", "seq", name="installments_loan_seq_key"),
        CheckConstraint(
            "principal_paid >= 0 AND interest_paid >= 0 AND fee_paid >= 0",
            name="installments_paid_non_negative",
        ),
        CheckConstraint(
            "principal_paid <= principal_due AND interest_paid <= interest_due",
            name="installments_not_overpaid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    loan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loans.id"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)  # 1 … term_count
    due_date: Mapped[date] = mapped_column(Date, index=True)
    principal_due: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    interest_due: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount_due: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # = principal + interest
    principal_paid: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    interest_paid: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    fee_paid: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )

    loan: Mapped[Loan] = relationship(back_populates="installments")
    allocations: Mapped[list["RepaymentAllocation"]] = relationship(
        back_populates="installment"
    )


# ---------------------------------------------------------------------------
# 2.5 repayments — append-only; one row per payment received
# ---------------------------------------------------------------------------


class Repayment(Base):
    __tablename__ = "repayments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="repayments_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    receipt_no: Mapped[str] = mapped_column(Text, unique=True)  # R-000001
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_on: Mapped[date] = mapped_column(Date)  # drives fee calculation
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=_enum_values)
    )
    note: Mapped[str | None] = mapped_column(Text)
    received_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loan: Mapped[Loan] = relationship(back_populates="repayments")
    allocations: Mapped[list["RepaymentAllocation"]] = relationship(
        back_populates="repayment"
    )
    receiver: Mapped[User] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# 2.6 repayment_allocations — append-only; the transparency table
# ---------------------------------------------------------------------------


class RepaymentAllocation(Base):
    __tablename__ = "repayment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "repayment_id", "installment_id", name="allocations_repayment_installment_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    repayment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repayments.id"), index=True
    )
    installment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("installments.id"), index=True
    )
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    interest_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )
    principal_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default=text("0.00")
    )

    repayment: Mapped[Repayment] = relationship(back_populates="allocations")
    installment: Mapped[Installment] = relationship(back_populates="allocations")


# ---------------------------------------------------------------------------
# 2.7 ledger_entries — append-only; every movement of money in one place
# ---------------------------------------------------------------------------


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ledger_entries_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, name="ledger_entry_type", values_callable=_enum_values)
    )
    direction: Mapped[LedgerDirection] = mapped_column(
        Enum(LedgerDirection, name="ledger_direction", values_callable=_enum_values)
    )
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    occurred_on: Mapped[date] = mapped_column(Date)  # the business date
    source_id: Mapped[uuid.UUID]  # loans.id or repayments.id that caused it
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 2.8 audit_log — append-only; written inside the same transaction as the change
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    action: Mapped[str] = mapped_column(Text)  # MEMBER_CREATED, LOAN_APPROVED, …
    entity_type: Mapped[str] = mapped_column(Text)  # member | loan | repayment | user
    entity_id: Mapped[uuid.UUID]
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    actor: Mapped[User] = relationship(lazy="joined")
