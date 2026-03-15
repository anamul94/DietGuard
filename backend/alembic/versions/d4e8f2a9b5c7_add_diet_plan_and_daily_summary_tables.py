"""add_diet_plan_and_daily_summary_tables

Revision ID: d4e8f2a9b5c7
Revises: c9e4f7a1b2d3
Create Date: 2026-03-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e8f2a9b5c7"
down_revision = "c9e4f7a1b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diet_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("generated_by", sa.String(length=50), nullable=False, server_default="diet_plan_agent_v1"),
        sa.Column("trigger", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_report_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("calorie_target", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diet_plans_id"), "diet_plans", ["id"], unique=False)
    op.create_index(op.f("ix_diet_plans_user_id"), "diet_plans", ["user_id"], unique=False)
    op.create_index(op.f("ix_diet_plans_valid_from"), "diet_plans", ["valid_from"], unique=False)
    op.create_index(op.f("ix_diet_plans_valid_until"), "diet_plans", ["valid_until"], unique=False)
    op.create_index(op.f("ix_diet_plans_is_active"), "diet_plans", ["is_active"], unique=False)
    op.create_index("idx_diet_plans_user_active", "diet_plans", ["user_id", "is_active"], unique=False)
    op.create_index("idx_diet_plans_user_validity", "diet_plans", ["user_id", "valid_from", "valid_until"], unique=False)

    op.create_table(
        "diet_plan_meals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diet_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("meal_type", sa.String(length=50), nullable=False),
        sa.Column("meal_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("foods", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_calories", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_protein_g", sa.Numeric(precision=10, scale=2), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["diet_plan_id"], ["diet_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diet_plan_meals_id"), "diet_plan_meals", ["id"], unique=False)
    op.create_index(op.f("ix_diet_plan_meals_diet_plan_id"), "diet_plan_meals", ["diet_plan_id"], unique=False)
    op.create_index(op.f("ix_diet_plan_meals_day_of_week"), "diet_plan_meals", ["day_of_week"], unique=False)
    op.create_index(op.f("ix_diet_plan_meals_meal_type"), "diet_plan_meals", ["meal_type"], unique=False)

    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("stats_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("adherence_score", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("alerts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("data_quality", sa.String(length=50), nullable=False, server_default="sufficient"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_summaries_id"), "daily_summaries", ["id"], unique=False)
    op.create_index(op.f("ix_daily_summaries_user_id"), "daily_summaries", ["user_id"], unique=False)
    op.create_index(op.f("ix_daily_summaries_summary_date"), "daily_summaries", ["summary_date"], unique=False)
    op.create_index("idx_daily_summaries_user_date", "daily_summaries", ["user_id", "summary_date"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_daily_summaries_user_date", table_name="daily_summaries")
    op.drop_index(op.f("ix_daily_summaries_summary_date"), table_name="daily_summaries")
    op.drop_index(op.f("ix_daily_summaries_user_id"), table_name="daily_summaries")
    op.drop_index(op.f("ix_daily_summaries_id"), table_name="daily_summaries")
    op.drop_table("daily_summaries")

    op.drop_index(op.f("ix_diet_plan_meals_meal_type"), table_name="diet_plan_meals")
    op.drop_index(op.f("ix_diet_plan_meals_day_of_week"), table_name="diet_plan_meals")
    op.drop_index(op.f("ix_diet_plan_meals_diet_plan_id"), table_name="diet_plan_meals")
    op.drop_index(op.f("ix_diet_plan_meals_id"), table_name="diet_plan_meals")
    op.drop_table("diet_plan_meals")

    op.drop_index("idx_diet_plans_user_validity", table_name="diet_plans")
    op.drop_index("idx_diet_plans_user_active", table_name="diet_plans")
    op.drop_index(op.f("ix_diet_plans_is_active"), table_name="diet_plans")
    op.drop_index(op.f("ix_diet_plans_valid_until"), table_name="diet_plans")
    op.drop_index(op.f("ix_diet_plans_valid_from"), table_name="diet_plans")
    op.drop_index(op.f("ix_diet_plans_user_id"), table_name="diet_plans")
    op.drop_index(op.f("ix_diet_plans_id"), table_name="diet_plans")
    op.drop_table("diet_plans")
