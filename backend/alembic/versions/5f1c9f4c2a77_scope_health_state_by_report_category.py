"""scope_health_state_by_report_category

Revision ID: 5f1c9f4c2a77
Revises: 02c57b282908
Create Date: 2026-03-14 23:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5f1c9f4c2a77"
down_revision = "02c57b282908"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in (
        "medical_reports",
        "medical_report_entities",
        "medical_condition_snapshots",
        "lab_results",
        "medication_schedules",
    ):
        op.add_column(
            table_name,
            sa.Column("report_category", sa.String(length=50), nullable=False, server_default="general"),
        )

    op.create_index(op.f("ix_medical_reports_report_category"), "medical_reports", ["report_category"], unique=False)
    op.create_index(
        "idx_medical_reports_user_current_category",
        "medical_reports",
        ["user_id", "report_category", "is_current"],
        unique=False,
    )

    op.create_index(op.f("ix_medical_report_entities_report_category"), "medical_report_entities", ["report_category"], unique=False)
    op.create_index(
        "idx_report_entities_user_current_category",
        "medical_report_entities",
        ["user_id", "report_category", "is_current"],
        unique=False,
    )

    op.create_index(
        op.f("ix_medical_condition_snapshots_report_category"),
        "medical_condition_snapshots",
        ["report_category"],
        unique=False,
    )
    op.create_index(
        "idx_condition_snapshots_user_current_category",
        "medical_condition_snapshots",
        ["user_id", "report_category", "is_current"],
        unique=False,
    )

    op.create_index(op.f("ix_lab_results_report_category"), "lab_results", ["report_category"], unique=False)
    op.create_index(
        "idx_lab_results_user_current_category",
        "lab_results",
        ["user_id", "report_category", "is_current"],
        unique=False,
    )

    op.create_index(op.f("ix_medication_schedules_report_category"), "medication_schedules", ["report_category"], unique=False)
    op.create_index(
        "idx_medication_schedules_user_current_category",
        "medication_schedules",
        ["user_id", "report_category", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_medication_schedules_user_current_category", table_name="medication_schedules")
    op.drop_index(op.f("ix_medication_schedules_report_category"), table_name="medication_schedules")

    op.drop_index("idx_lab_results_user_current_category", table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_report_category"), table_name="lab_results")

    op.drop_index("idx_condition_snapshots_user_current_category", table_name="medical_condition_snapshots")
    op.drop_index(op.f("ix_medical_condition_snapshots_report_category"), table_name="medical_condition_snapshots")

    op.drop_index("idx_report_entities_user_current_category", table_name="medical_report_entities")
    op.drop_index(op.f("ix_medical_report_entities_report_category"), table_name="medical_report_entities")

    op.drop_index("idx_medical_reports_user_current_category", table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_report_category"), table_name="medical_reports")

    for table_name in (
        "medication_schedules",
        "lab_results",
        "medical_condition_snapshots",
        "medical_report_entities",
        "medical_reports",
    ):
        op.drop_column(table_name, "report_category")
