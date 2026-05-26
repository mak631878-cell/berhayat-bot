"""001_initial_schema

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── employees ──────────────────────────────────────────────────────────
    op.create_table(
        "employees",
        sa.Column("id",           sa.Integer(),     nullable=False, primary_key=True),
        sa.Column("telegram_id",  sa.BigInteger(),  nullable=True,  unique=True),
        sa.Column("fio",          sa.String(255),   nullable=False),
        sa.Column("birth_date",   sa.Date(),        nullable=True),
        sa.Column("city",         sa.String(100),   nullable=True),
        sa.Column("phone",        sa.String(30),    nullable=True),
        sa.Column("education",    sa.Text(),        nullable=True),
        sa.Column("photo_url",    sa.String(512),   nullable=True),
        sa.Column("role",
            postgresql.ENUM("owner", "manager", "sales", name="rolename", create_type=True),
            nullable=False,
            server_default="sales",
        ),
        sa.Column("position",     sa.String(200),   nullable=True),
        sa.Column("salary",       sa.Numeric(12,2), nullable=True),
        sa.Column("is_active",    sa.Boolean(),     nullable=False, server_default="false"),
        sa.Column("invite_token", sa.String(64),    nullable=True,  unique=True),
        sa.Column("invited_by",   sa.Integer(),     sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("consent_pd",   sa.Boolean(),     nullable=False, server_default="false"),
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── clients ────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id",         sa.Integer(),    nullable=False, primary_key=True),
        sa.Column("name",       sa.String(255),  nullable=False),
        sa.Column("phone",      sa.String(30),   nullable=True),
        sa.Column("city",       sa.String(100),  nullable=True),
        sa.Column("source",     sa.String(100),  nullable=True),
        sa.Column("created_by", sa.Integer(),    sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── services ───────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id",          sa.Integer(),    nullable=False, primary_key=True),
        sa.Column("name",        sa.String(255),  nullable=False),
        sa.Column("price",       sa.Numeric(12,2),nullable=False),
        sa.Column("description", sa.Text(),       nullable=True),
        sa.Column("is_active",   sa.Boolean(),    server_default="true"),
    )

    # ── deals ──────────────────────────────────────────────────────────────
    op.create_table(
        "deals",
        sa.Column("id",          sa.Integer(),    nullable=False, primary_key=True),
        sa.Column("client_id",   sa.Integer(),    sa.ForeignKey("clients.id"),   nullable=False),
        sa.Column("employee_id", sa.Integer(),    sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("service_id",  sa.Integer(),    sa.ForeignKey("services.id"),  nullable=True),
        sa.Column("amount",      sa.Numeric(14,2),nullable=False),
        sa.Column("status",
            postgresql.ENUM("new", "in_work", "won", "lost", name="dealstatus", create_type=True),
            nullable=False,
            server_default="new",
        ),
        sa.Column("notes",      sa.Text(),        nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── documents ──────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id",         sa.Integer(),   nullable=False, primary_key=True),
        sa.Column("deal_id",    sa.Integer(),   sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("type",
            postgresql.ENUM("contract", "act", "commercial", "invoice", name="doctype", create_type=True),
            nullable=False,
        ),
        sa.Column("file_url",   sa.String(512), nullable=False),
        sa.Column("created_by", sa.Integer(),   sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── shifts ─────────────────────────────────────────────────────────────
    op.create_table(
        "shifts",
        sa.Column("id",          sa.Integer(), nullable=False, primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("date",        sa.Date(),    nullable=False),
        sa.Column("is_on_shift", sa.Boolean(), server_default="true"),
        sa.UniqueConstraint("employee_id", "date", name="uq_shift_emp_date"),
    )

    # ── logs ───────────────────────────────────────────────────────────────
    op.create_table(
        "logs",
        sa.Column("id",          sa.Integer(),   nullable=False, primary_key=True),
        sa.Column("employee_id", sa.Integer(),   sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("action",      sa.String(200), nullable=False),
        sa.Column("details",     sa.Text(),      nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Индексы ────────────────────────────────────────────────────────────
    op.create_index("ix_deals_employee_id",   "deals",    ["employee_id"])
    op.create_index("ix_deals_client_id",     "deals",    ["client_id"])
    op.create_index("ix_documents_deal_id",   "documents",["deal_id"])
    op.create_index("ix_logs_employee_id",    "logs",     ["employee_id"])
    op.create_index("ix_logs_created_at",     "logs",     ["created_at"])


def downgrade() -> None:
    op.drop_table("logs")
    op.drop_table("shifts")
    op.drop_table("documents")
    op.drop_table("deals")
    op.drop_table("services")
    op.drop_table("clients")
    op.drop_table("employees")
    op.execute("DROP TYPE IF EXISTS rolename")
    op.execute("DROP TYPE IF EXISTS dealstatus")
    op.execute("DROP TYPE IF EXISTS doctype")
