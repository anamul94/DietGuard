"""add_longitudinal_health_tables

Revision ID: b3d2a4e7c9f1
Revises: 7cb87dd40631
Create Date: 2026-03-13 18:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b3d2a4e7c9f1"
down_revision = "7cb87dd40631"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("filenames", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structured_summary", sa.Text(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_medical_reports_user_version", "medical_reports", ["user_id", "version"], unique=True)
    op.create_index("idx_medical_reports_user_current", "medical_reports", ["user_id", "is_current"], unique=False)
    op.create_index(op.f("ix_medical_reports_id"), "medical_reports", ["id"], unique=False)
    op.create_index(op.f("ix_medical_reports_is_current"), "medical_reports", ["is_current"], unique=False)
    op.create_index(op.f("ix_medical_reports_report_date"), "medical_reports", ["report_date"], unique=False)
    op.create_index(op.f("ix_medical_reports_user_id"), "medical_reports", ["user_id"], unique=False)

    op.create_table(
        "medical_condition_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_report_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("diabetes_status", sa.String(length=20), nullable=False),
        sa.Column("hypertension_status", sa.String(length=20), nullable=False),
        sa.Column("kidney_disease_stage", sa.String(length=50), nullable=True),
        sa.Column("dyslipidemia_status", sa.String(length=20), nullable=False),
        sa.Column("food_restrictions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allergies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dietary_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("doctor_advice", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extra_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_report_id"], ["medical_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_condition_snapshots_user_current", "medical_condition_snapshots", ["user_id", "is_current"], unique=False)
    op.create_index(op.f("ix_medical_condition_snapshots_id"), "medical_condition_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_medical_condition_snapshots_is_current"), "medical_condition_snapshots", ["is_current"], unique=False)
    op.create_index(op.f("ix_medical_condition_snapshots_snapshot_date"), "medical_condition_snapshots", ["snapshot_date"], unique=False)
    op.create_index(op.f("ix_medical_condition_snapshots_source_report_id"), "medical_condition_snapshots", ["source_report_id"], unique=False)
    op.create_index(op.f("ix_medical_condition_snapshots_user_id"), "medical_condition_snapshots", ["user_id"], unique=False)

    op.create_table(
        "lab_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_report_id", sa.UUID(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("lab_date", sa.Date(), nullable=True),
        sa.Column("test_name", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=100), nullable=True),
        sa.Column("value_numeric", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("value_text", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("reference_range", sa.String(length=100), nullable=True),
        sa.Column("interpretation", sa.String(length=100), nullable=True),
        sa.Column("abnormal_flag", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_report_id"], ["medical_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lab_results_user_canonical_date", "lab_results", ["user_id", "canonical_name", "lab_date"], unique=False)
    op.create_index(op.f("ix_lab_results_canonical_name"), "lab_results", ["canonical_name"], unique=False)
    op.create_index(op.f("ix_lab_results_id"), "lab_results", ["id"], unique=False)
    op.create_index(op.f("ix_lab_results_is_current"), "lab_results", ["is_current"], unique=False)
    op.create_index(op.f("ix_lab_results_lab_date"), "lab_results", ["lab_date"], unique=False)
    op.create_index(op.f("ix_lab_results_source_report_id"), "lab_results", ["source_report_id"], unique=False)
    op.create_index(op.f("ix_lab_results_user_id"), "lab_results", ["user_id"], unique=False)

    op.create_table(
        "medication_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_report_id", sa.UUID(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("medication_name", sa.String(length=255), nullable=False),
        sa.Column("dosage", sa.String(length=100), nullable=True),
        sa.Column("schedule", sa.String(length=100), nullable=True),
        sa.Column("timing_notes", sa.String(length=255), nullable=True),
        sa.Column("with_food", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_report_id"], ["medical_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_medication_schedules_user_current", "medication_schedules", ["user_id", "is_current"], unique=False)
    op.create_index(op.f("ix_medication_schedules_id"), "medication_schedules", ["id"], unique=False)
    op.create_index(op.f("ix_medication_schedules_is_current"), "medication_schedules", ["is_current"], unique=False)
    op.create_index(op.f("ix_medication_schedules_source_report_id"), "medication_schedules", ["source_report_id"], unique=False)
    op.create_index(op.f("ix_medication_schedules_user_id"), "medication_schedules", ["user_id"], unique=False)

    op.create_table(
        "meal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("meal_date", sa.Date(), nullable=False),
        sa.Column("meal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_calories", sa.Integer(), nullable=False),
        sa.Column("total_protein_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_carbohydrates_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_fat_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_fiber_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_sugar_g", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_meal_events_user_date", "meal_events", ["user_id", "meal_date"], unique=False)
    op.create_index(op.f("ix_meal_events_id"), "meal_events", ["id"], unique=False)
    op.create_index(op.f("ix_meal_events_meal_date"), "meal_events", ["meal_date"], unique=False)
    op.create_index(op.f("ix_meal_events_meal_time"), "meal_events", ["meal_time"], unique=False)
    op.create_index(op.f("ix_meal_events_meal_type"), "meal_events", ["meal_type"], unique=False)
    op.create_index(op.f("ix_meal_events_user_id"), "meal_events", ["user_id"], unique=False)

    op.create_table(
        "meal_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("meal_event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("preparation", sa.String(length=255), nullable=True),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("is_user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meal_items_id"), "meal_items", ["id"], unique=False)
    op.create_index(op.f("ix_meal_items_meal_event_id"), "meal_items", ["meal_event_id"], unique=False)
    op.create_index(op.f("ix_meal_items_user_id"), "meal_items", ["user_id"], unique=False)

    op.create_table(
        "meal_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("meal_event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meal_media_id"), "meal_media", ["id"], unique=False)
    op.create_index(op.f("ix_meal_media_meal_event_id"), "meal_media", ["meal_event_id"], unique=False)
    op.create_index(op.f("ix_meal_media_user_id"), "meal_media", ["user_id"], unique=False)

    op.create_table(
        "vital_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_device", sa.String(length=100), nullable=True),
        sa.Column("vital_type", sa.String(length=50), nullable=False),
        sa.Column("value_primary", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("value_secondary", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_vital_events_user_captured", "vital_events", ["user_id", "captured_at"], unique=False)
    op.create_index(op.f("ix_vital_events_captured_at"), "vital_events", ["captured_at"], unique=False)
    op.create_index(op.f("ix_vital_events_id"), "vital_events", ["id"], unique=False)
    op.create_index(op.f("ix_vital_events_source"), "vital_events", ["source"], unique=False)
    op.create_index(op.f("ix_vital_events_user_id"), "vital_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_vital_events_vital_type"), "vital_events", ["vital_type"], unique=False)

    op.create_table(
        "mood_checkins",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("audio_filename", sa.String(length=255), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("mood_label", sa.String(length=50), nullable=True),
        sa.Column("energy_level", sa.Integer(), nullable=True),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("symptom_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mood_checkins_captured_at"), "mood_checkins", ["captured_at"], unique=False)
    op.create_index(op.f("ix_mood_checkins_id"), "mood_checkins", ["id"], unique=False)
    op.create_index(op.f("ix_mood_checkins_user_id"), "mood_checkins", ["user_id"], unique=False)

    op.create_table(
        "correlation_insights",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("meal_event_id", sa.UUID(), nullable=True),
        sa.Column("vital_event_id", sa.UUID(), nullable=True),
        sa.Column("mood_checkin_id", sa.UUID(), nullable=True),
        sa.Column("source_report_id", sa.UUID(), nullable=True),
        sa.Column("insight_date", sa.Date(), nullable=False),
        sa.Column("insight_kind", sa.String(length=50), nullable=False),
        sa.Column("confidence_tier", sa.String(length=20), nullable=False),
        sa.Column("association_label", sa.String(length=255), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("possible_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mood_checkin_id"], ["mood_checkins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_report_id"], ["medical_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vital_event_id"], ["vital_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_correlation_insights_user_date", "correlation_insights", ["user_id", "insight_date"], unique=False)
    op.create_index(op.f("ix_correlation_insights_id"), "correlation_insights", ["id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_meal_event_id"), "correlation_insights", ["meal_event_id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_mood_checkin_id"), "correlation_insights", ["mood_checkin_id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_source_report_id"), "correlation_insights", ["source_report_id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_user_id"), "correlation_insights", ["user_id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_vital_event_id"), "correlation_insights", ["vital_event_id"], unique=False)
    op.create_index(op.f("ix_correlation_insights_insight_date"), "correlation_insights", ["insight_date"], unique=False)
    op.create_index(op.f("ix_correlation_insights_insight_kind"), "correlation_insights", ["insight_kind"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_correlation_insights_insight_kind"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_insight_date"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_vital_event_id"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_user_id"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_source_report_id"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_mood_checkin_id"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_meal_event_id"), table_name="correlation_insights")
    op.drop_index(op.f("ix_correlation_insights_id"), table_name="correlation_insights")
    op.drop_index("idx_correlation_insights_user_date", table_name="correlation_insights")
    op.drop_table("correlation_insights")

    op.drop_index(op.f("ix_mood_checkins_user_id"), table_name="mood_checkins")
    op.drop_index(op.f("ix_mood_checkins_id"), table_name="mood_checkins")
    op.drop_index(op.f("ix_mood_checkins_captured_at"), table_name="mood_checkins")
    op.drop_table("mood_checkins")

    op.drop_index(op.f("ix_vital_events_vital_type"), table_name="vital_events")
    op.drop_index(op.f("ix_vital_events_user_id"), table_name="vital_events")
    op.drop_index(op.f("ix_vital_events_source"), table_name="vital_events")
    op.drop_index(op.f("ix_vital_events_id"), table_name="vital_events")
    op.drop_index(op.f("ix_vital_events_captured_at"), table_name="vital_events")
    op.drop_index("idx_vital_events_user_captured", table_name="vital_events")
    op.drop_table("vital_events")

    op.drop_index(op.f("ix_meal_media_user_id"), table_name="meal_media")
    op.drop_index(op.f("ix_meal_media_meal_event_id"), table_name="meal_media")
    op.drop_index(op.f("ix_meal_media_id"), table_name="meal_media")
    op.drop_table("meal_media")

    op.drop_index(op.f("ix_meal_items_user_id"), table_name="meal_items")
    op.drop_index(op.f("ix_meal_items_meal_event_id"), table_name="meal_items")
    op.drop_index(op.f("ix_meal_items_id"), table_name="meal_items")
    op.drop_table("meal_items")

    op.drop_index(op.f("ix_meal_events_user_id"), table_name="meal_events")
    op.drop_index(op.f("ix_meal_events_meal_type"), table_name="meal_events")
    op.drop_index(op.f("ix_meal_events_meal_time"), table_name="meal_events")
    op.drop_index(op.f("ix_meal_events_meal_date"), table_name="meal_events")
    op.drop_index(op.f("ix_meal_events_id"), table_name="meal_events")
    op.drop_index("idx_meal_events_user_date", table_name="meal_events")
    op.drop_table("meal_events")

    op.drop_index(op.f("ix_medication_schedules_user_id"), table_name="medication_schedules")
    op.drop_index(op.f("ix_medication_schedules_source_report_id"), table_name="medication_schedules")
    op.drop_index(op.f("ix_medication_schedules_is_current"), table_name="medication_schedules")
    op.drop_index(op.f("ix_medication_schedules_id"), table_name="medication_schedules")
    op.drop_index("idx_medication_schedules_user_current", table_name="medication_schedules")
    op.drop_table("medication_schedules")

    op.drop_index(op.f("ix_lab_results_user_id"), table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_source_report_id"), table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_lab_date"), table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_is_current"), table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_id"), table_name="lab_results")
    op.drop_index(op.f("ix_lab_results_canonical_name"), table_name="lab_results")
    op.drop_index("idx_lab_results_user_canonical_date", table_name="lab_results")
    op.drop_table("lab_results")

    op.drop_index(op.f("ix_medical_condition_snapshots_user_id"), table_name="medical_condition_snapshots")
    op.drop_index(op.f("ix_medical_condition_snapshots_source_report_id"), table_name="medical_condition_snapshots")
    op.drop_index(op.f("ix_medical_condition_snapshots_snapshot_date"), table_name="medical_condition_snapshots")
    op.drop_index(op.f("ix_medical_condition_snapshots_is_current"), table_name="medical_condition_snapshots")
    op.drop_index(op.f("ix_medical_condition_snapshots_id"), table_name="medical_condition_snapshots")
    op.drop_index("idx_condition_snapshots_user_current", table_name="medical_condition_snapshots")
    op.drop_table("medical_condition_snapshots")

    op.drop_index(op.f("ix_medical_reports_user_id"), table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_report_date"), table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_is_current"), table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_id"), table_name="medical_reports")
    op.drop_index("idx_medical_reports_user_current", table_name="medical_reports")
    op.drop_index("idx_medical_reports_user_version", table_name="medical_reports")
    op.drop_table("medical_reports")
