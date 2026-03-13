"""add_medical_report_entities_table

Revision ID: c4f7d9a2b1e3
Revises: b3d2a4e7c9f1
Create Date: 2026-03-13 19:20:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c4f7d9a2b1e3"
down_revision = "b3d2a4e7c9f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_report_entities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_report_id", sa.UUID(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=100), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("reference_range", sa.String(length=255), nullable=True),
        sa.Column("interpretation", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_section", sa.String(length=255), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_report_id"], ["medical_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_report_entities_user_current_type",
        "medical_report_entities",
        ["user_id", "is_current", "entity_type"],
        unique=False,
    )
    op.create_index(
        "idx_report_entities_user_canonical_date",
        "medical_report_entities",
        ["user_id", "canonical_name", "effective_date"],
        unique=False,
    )
    op.create_index(op.f("ix_medical_report_entities_id"), "medical_report_entities", ["id"], unique=False)
    op.create_index(
        op.f("ix_medical_report_entities_user_id"),
        "medical_report_entities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_source_report_id"),
        "medical_report_entities",
        ["source_report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_is_current"),
        "medical_report_entities",
        ["is_current"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_entity_type"),
        "medical_report_entities",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_category"),
        "medical_report_entities",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_canonical_name"),
        "medical_report_entities",
        ["canonical_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_report_entities_effective_date"),
        "medical_report_entities",
        ["effective_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_medical_report_entities_effective_date"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_canonical_name"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_category"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_entity_type"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_is_current"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_source_report_id"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_user_id"), table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_id"), table_name="medical_report_entities")
    op.drop_index("idx_report_entities_user_canonical_date", table_name="medical_report_entities")
    op.drop_index("idx_report_entities_user_current_type", table_name="medical_report_entities")
    op.drop_table("medical_report_entities")
