"""add_nutrition_targets_and_persona_fields

Revision ID: c9e4f7a1b2d3
Revises: 8a44d0f5501f
Create Date: 2026-03-15 03:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c9e4f7a1b2d3"
down_revision = "8a44d0f5501f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_persona",
        sa.Column("activity_level", sa.String(length=20), nullable=False, server_default="sedentary"),
    )
    op.add_column(
        "patient_persona",
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
    )

    op.create_table(
        "nutrition_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("calories_kcal", sa.Integer(), nullable=False),
        sa.Column("protein_g", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("carbohydrates_g", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("fat_g", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("fiber_g", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="calculated"),
        sa.Column("calculation_basis", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_nutrition_targets_id"), "nutrition_targets", ["id"], unique=False)
    op.create_index(op.f("ix_nutrition_targets_is_active"), "nutrition_targets", ["is_active"], unique=False)
    op.create_index(op.f("ix_nutrition_targets_target_date"), "nutrition_targets", ["target_date"], unique=False)
    op.create_index(op.f("ix_nutrition_targets_user_id"), "nutrition_targets", ["user_id"], unique=False)
    op.create_index("idx_nutrition_targets_user_active", "nutrition_targets", ["user_id", "is_active"], unique=False)
    op.create_index("idx_nutrition_targets_user_target_date", "nutrition_targets", ["user_id", "target_date"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_nutrition_targets_user_target_date", table_name="nutrition_targets")
    op.drop_index("idx_nutrition_targets_user_active", table_name="nutrition_targets")
    op.drop_index(op.f("ix_nutrition_targets_user_id"), table_name="nutrition_targets")
    op.drop_index(op.f("ix_nutrition_targets_target_date"), table_name="nutrition_targets")
    op.drop_index(op.f("ix_nutrition_targets_is_active"), table_name="nutrition_targets")
    op.drop_index(op.f("ix_nutrition_targets_id"), table_name="nutrition_targets")
    op.drop_table("nutrition_targets")

    op.drop_column("patient_persona", "timezone")
    op.drop_column("patient_persona", "activity_level")
