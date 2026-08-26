"""Initial schema — every table, constraint, index, and trigger.

Mirrors DATABASE.md §2–3 exactly. Hand-written and hand-reviewed: autogenerate
cannot produce the partial unique index, the append-only triggers, or the trigram
index, so those live here on purpose.

Revision ID: 0001
Revises:
Create Date: 2026-08-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    # --- 2.1 users -----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "OFFICER", "CASHIER", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # --- 2.2 members ---------------------------------------------------------
    op.create_table(
        "members",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("member_code", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("national_id", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="member_status"), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_code"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("national_id"),
    )

    # Search: trigram index on names; phone search rides the unique index.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX members_full_name_trgm ON members USING gin (full_name gin_trgm_ops)"
    )

    # --- 2.3 loans -----------------------------------------------------------
    op.create_table(
        "loans",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("loan_code", sa.Text(), nullable=False),
        sa.Column("member_id", UUID(as_uuid=True), nullable=False),
        sa.Column("principal", MONEY, nullable=False),
        sa.Column("interest_rate_annual", sa.Numeric(5, 2), nullable=False),
        sa.Column("term_count", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.Enum("WEEKLY", "MONTHLY", name="loan_frequency"), nullable=False),
        sa.Column("late_fee", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.Column("grace_days", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("total_interest", MONEY, nullable=True),
        sa.Column("total_payable", MONEY, nullable=True),
        sa.Column("installment_amount", MONEY, nullable=True),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", "DISBURSED", "CLOSED", name="loan_status"), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("disbursed_on", sa.Date(), nullable=True),
        sa.Column("disbursed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["disbursed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_code"),
        sa.CheckConstraint("principal > 0", name="loans_principal_positive"),
        sa.CheckConstraint("term_count > 0", name="loans_term_positive"),
        sa.CheckConstraint("interest_rate_annual >= 0", name="loans_rate_non_negative"),
        sa.CheckConstraint(
            "status <> 'REJECTED' OR rejection_reason IS NOT NULL",
            name="loans_rejection_has_reason",
        ),
        sa.CheckConstraint(
            "status NOT IN ('DISBURSED', 'CLOSED') "
            "OR (disbursed_on IS NOT NULL AND total_payable IS NOT NULL)",
            name="loans_disbursed_has_terms",
        ),
        sa.CheckConstraint(
            "disbursed_on IS NULL OR disbursed_on >= applied_on",
            name="loans_disbursed_after_applied",
        ),
    )
    op.create_index("loans_member_id_idx", "loans", ["member_id"])
    op.create_index("loans_status_idx", "loans", ["status"])
    # R2: one active loan per member — enforced by Postgres, not by Python.
    op.create_index(
        "one_active_loan_per_member",
        "loans",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED', 'DISBURSED')"),
    )

    # --- 2.4 installments ------------------------------------------------------
    op.create_table(
        "installments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("loan_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("principal_due", MONEY, nullable=False),
        sa.Column("interest_due", MONEY, nullable=False),
        sa.Column("amount_due", MONEY, nullable=False),
        sa.Column("principal_paid", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.Column("interest_paid", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.Column("fee_paid", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.ForeignKeyConstraint(["loan_id"], ["loans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_id", "seq", name="installments_loan_seq_key"),
        sa.CheckConstraint(
            "principal_paid >= 0 AND interest_paid >= 0 AND fee_paid >= 0",
            name="installments_paid_non_negative",
        ),
        sa.CheckConstraint(
            "principal_paid <= principal_due AND interest_paid <= interest_due",
            name="installments_not_overpaid",
        ),
    )
    op.create_index("installments_loan_id_idx", "installments", ["loan_id"])
    op.create_index("installments_due_date_idx", "installments", ["due_date"])

    # --- 2.5 repayments (append-only) -----------------------------------------
    op.create_table(
        "repayments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("receipt_no", sa.Text(), nullable=False),
        sa.Column("loan_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("method", sa.Enum("CASH", "BANK", "MOBILE", name="payment_method"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("received_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["loan_id"], ["loans.id"]),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_no"),
        sa.CheckConstraint("amount > 0", name="repayments_amount_positive"),
    )
    op.create_index("repayments_loan_id_idx", "repayments", ["loan_id"])

    # --- 2.6 repayment_allocations (append-only) -------------------------------
    op.create_table(
        "repayment_allocations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repayment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("installment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fee_amount", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.Column("interest_amount", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.Column("principal_amount", MONEY, server_default=sa.text("0.00"), nullable=False),
        sa.ForeignKeyConstraint(["repayment_id"], ["repayments.id"]),
        sa.ForeignKeyConstraint(["installment_id"], ["installments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repayment_id", "installment_id", name="allocations_repayment_installment_key"),
    )
    op.create_index("allocations_repayment_id_idx", "repayment_allocations", ["repayment_id"])
    op.create_index("allocations_installment_id_idx", "repayment_allocations", ["installment_id"])

    # --- 2.7 ledger_entries (append-only) ---------------------------------------
    op.create_table(
        "ledger_entries",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("entry_type", sa.Enum("DISBURSEMENT", "REPAYMENT", name="ledger_entry_type"), nullable=False),
        sa.Column("direction", sa.Enum("OUT", "IN", name="ledger_direction"), nullable=False),
        sa.Column("loan_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["loan_id"], ["loans.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount > 0", name="ledger_entries_amount_positive"),
    )
    op.create_index("ledger_entries_loan_id_idx", "ledger_entries", ["loan_id"])
    op.create_index("ledger_entries_entry_type_idx", "ledger_entries", ["entry_type"])

    # --- 2.8 audit_log (append-only) --------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("before", JSONB(), nullable=True),
        sa.Column("after", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("audit_log_actor_user_id_idx", "audit_log", ["actor_user_id"])
    op.execute(
        "CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id, occurred_at DESC)"
    )

    # --- 3.1 the append-only ledger ---------------------------------------------
    op.execute(
        """
        CREATE FUNCTION reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is append-only; % is not permitted',
                            TG_TABLE_NAME, TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table, trigger in [
        ("repayments", "repayments_append_only"),
        ("repayment_allocations", "allocations_append_only"),
        ("ledger_entries", "ledger_append_only"),
        ("audit_log", "audit_log_append_only"),
    ]:
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION reject_mutation();
            """
        )


def downgrade() -> None:
    for table, trigger in [
        ("repayments", "repayments_append_only"),
        ("repayment_allocations", "allocations_append_only"),
        ("ledger_entries", "ledger_append_only"),
        ("audit_log", "audit_log_append_only"),
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_mutation()")

    op.drop_table("audit_log")
    op.drop_table("ledger_entries")
    op.drop_table("repayment_allocations")
    op.drop_table("repayments")
    op.drop_table("installments")
    op.drop_index("one_active_loan_per_member", table_name="loans")
    op.drop_index("loans_status_idx", table_name="loans")
    op.drop_index("loans_member_id_idx", table_name="loans")
    op.drop_table("loans")
    op.execute("DROP INDEX IF EXISTS members_full_name_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.drop_table("members")
    op.drop_table("users")

    for enum_name in [
        "ledger_direction",
        "ledger_entry_type",
        "payment_method",
        "loan_status",
        "loan_frequency",
        "member_status",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
