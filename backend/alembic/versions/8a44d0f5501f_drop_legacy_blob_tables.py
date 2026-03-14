"""drop_legacy_blob_tables

Revision ID: 8a44d0f5501f
Revises: 5f1c9f4c2a77
Create Date: 2026-03-15 00:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8a44d0f5501f"
down_revision = "5f1c9f4c2a77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS nutrition_data CASCADE")
    op.execute("DROP TABLE IF EXISTS report_data CASCADE")


def downgrade() -> None:
    op.create_table(
        "report_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_data_id"), "report_data", ["id"], unique=False)
    op.create_index(op.f("ix_report_data_user_id"), "report_data", ["user_id"], unique=False)

    op.create_table(
        "nutrition_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meal_time", sa.Time(), nullable=True),
        sa.Column("meal_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_nutrition_data_user_date", "nutrition_data", ["user_id", "meal_date"], unique=False)
    op.create_index(op.f("ix_nutrition_data_id"), "nutrition_data", ["id"], unique=False)
    op.create_index(op.f("ix_nutrition_data_meal_date"), "nutrition_data", ["meal_date"], unique=False)
    op.create_index(op.f("ix_nutrition_data_user_id"), "nutrition_data", ["user_id"], unique=False)
