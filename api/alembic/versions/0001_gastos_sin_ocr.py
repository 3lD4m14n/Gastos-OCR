"""Usuarios, categorías y gastos.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.migrations import create_index

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text()),
        sa.Column("name", sa.Text()),
        sa.Column("currency", sa.Text(), server_default="PYG", nullable=False),
        sa.Column("timezone", sa.Text(), server_default="America/Asuncion", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text()),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_categories_user_name"),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("search_key", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), server_default="1", nullable=False),
        sa.Column("unit_price", sa.BigInteger()),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("iva_rate", sa.SmallInteger()),
        sa.Column("spent_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )
    create_index(
        "uq_categories_one_fallback", "categories", ["user_id"], unique=True, where="is_fallback"
    )
    create_index("ix_expenses_user_spent_at", "expenses", ["user_id", "spent_at"])


def downgrade() -> None:
    op.drop_table("expenses")
    op.drop_table("categories")
    op.drop_table("users")
