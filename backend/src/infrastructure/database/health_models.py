"""
Longitudinal health timeline models.

These tables extend DietGuard from single-event blob storage into structured,
versioned health data that can power meal/vital/report correlations.
"""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class MedicalReport(Base):
    __tablename__ = "medical_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False, default="upload")
    parser_version = Column(String(50), nullable=False, default="report_agent_v2")
    filenames = Column(JSONB, nullable=False, default=list)
    raw_payload = Column(JSONB, nullable=False)
    structured_summary = Column(Text, nullable=True)
    report_date = Column(Date, nullable=True, index=True)
    report_category = Column(String(50), nullable=False, default="general", index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_medical_reports_user_version", "user_id", "version", unique=True),
        Index("idx_medical_reports_user_current", "user_id", "is_current"),
        Index("idx_medical_reports_user_current_category", "user_id", "report_category", "is_current"),
    )


class MedicalReportEntity(Base):
    __tablename__ = "medical_report_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey("medical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    report_category = Column(String(50), nullable=False, default="general", index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)
    label = Column(String(255), nullable=False)
    canonical_name = Column(String(100), nullable=True, index=True)
    value_text = Column(Text, nullable=True)
    value_numeric = Column(Numeric(12, 4), nullable=True)
    unit = Column(String(50), nullable=True)
    reference_range = Column(String(255), nullable=True)
    interpretation = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    effective_date = Column(Date, nullable=True, index=True)
    source_section = Column(String(255), nullable=True)
    source_text = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    confidence = Column(Numeric(4, 2), nullable=True)
    attributes = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_report_entities_user_current_type", "user_id", "is_current", "entity_type"),
        Index("idx_report_entities_user_current_category", "user_id", "report_category", "is_current"),
        Index("idx_report_entities_user_canonical_date", "user_id", "canonical_name", "effective_date"),
    )


class MedicalConditionSnapshot(Base):
    __tablename__ = "medical_condition_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey("medical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    report_category = Column(String(50), nullable=False, default="general", index=True)
    snapshot_date = Column(Date, nullable=True, index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    diabetes_status = Column(String(20), nullable=False, default="unknown")
    hypertension_status = Column(String(20), nullable=False, default="unknown")
    kidney_disease_stage = Column(String(50), nullable=True)
    dyslipidemia_status = Column(String(20), nullable=False, default="unknown")
    food_restrictions = Column(JSONB, nullable=False, default=list)
    allergies = Column(JSONB, nullable=False, default=list)
    dietary_preferences = Column(JSONB, nullable=False, default=list)
    doctor_advice = Column(JSONB, nullable=False, default=list)
    extra_conditions = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_condition_snapshots_user_current", "user_id", "is_current"),
        Index("idx_condition_snapshots_user_current_category", "user_id", "report_category", "is_current"),
    )


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey("medical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    report_category = Column(String(50), nullable=False, default="general", index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    lab_date = Column(Date, nullable=True, index=True)
    test_name = Column(String(255), nullable=False)
    canonical_name = Column(String(100), nullable=True, index=True)
    value_numeric = Column(Numeric(10, 2), nullable=True)
    value_text = Column(String(100), nullable=False)
    unit = Column(String(50), nullable=True)
    reference_range = Column(String(100), nullable=True)
    interpretation = Column(String(100), nullable=True)
    abnormal_flag = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_lab_results_user_current_category", "user_id", "report_category", "is_current"),
        Index("idx_lab_results_user_canonical_date", "user_id", "canonical_name", "lab_date"),
    )


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey("medical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    report_category = Column(String(50), nullable=False, default="general", index=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    medication_name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=True)
    schedule = Column(String(100), nullable=True)
    timing_notes = Column(String(255), nullable=True)
    with_food = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_medication_schedules_user_current", "user_id", "is_current"),
        Index("idx_medication_schedules_user_current_category", "user_id", "report_category", "is_current"),
    )


class MealEvent(Base):
    __tablename__ = "meal_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_type = Column(String(20), nullable=False, index=True)
    meal_date = Column(Date, nullable=False, index=True)
    meal_time = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(50), nullable=False, default="image")
    status = Column(String(20), nullable=False, default="confirmed")
    total_calories = Column(Integer, nullable=False, default=0)
    total_protein_g = Column(Numeric(10, 2), nullable=True)
    total_carbohydrates_g = Column(Numeric(10, 2), nullable=True)
    total_fat_g = Column(Numeric(10, 2), nullable=True)
    total_fiber_g = Column(Numeric(10, 2), nullable=True)
    total_sugar_g = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items = relationship("MealItem", back_populates="meal_event", cascade="all, delete-orphan")
    media = relationship("MealMedia", back_populates="meal_event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_meal_events_user_date", "user_id", "meal_date"),
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    meal_event_id = Column(UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    quantity = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="main")
    preparation = Column(String(255), nullable=True)
    source_label = Column(String(255), nullable=True)
    confidence = Column(Numeric(4, 2), nullable=True)
    is_user_confirmed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    meal_event = relationship("MealEvent", back_populates="items")


class MealMedia(Base):
    __tablename__ = "meal_media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    meal_event_id = Column(UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False, default="image")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    meal_event = relationship("MealEvent", back_populates="media")


class VitalEvent(Base):
    __tablename__ = "vital_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(20), nullable=False, index=True)
    source_device = Column(String(100), nullable=True)
    vital_type = Column(String(50), nullable=False, index=True)
    value_primary = Column(Numeric(10, 2), nullable=False)
    value_secondary = Column(Numeric(10, 2), nullable=True)
    unit = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_vital_events_user_captured", "user_id", "captured_at"),
    )


class MoodCheckIn(Base):
    __tablename__ = "mood_checkins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(20), nullable=False, default="audio")
    audio_filename = Column(String(255), nullable=True)
    transcript = Column(Text, nullable=True)
    mood_label = Column(String(50), nullable=True)
    energy_level = Column(Integer, nullable=True)
    stress_level = Column(Integer, nullable=True)
    sleep_quality = Column(Integer, nullable=True)
    symptom_flags = Column(JSONB, nullable=False, default=list)
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CorrelationInsight(Base):
    __tablename__ = "correlation_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_event_id = Column(UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="SET NULL"), nullable=True, index=True)
    vital_event_id = Column(UUID(as_uuid=True), ForeignKey("vital_events.id", ondelete="SET NULL"), nullable=True, index=True)
    mood_checkin_id = Column(UUID(as_uuid=True), ForeignKey("mood_checkins.id", ondelete="SET NULL"), nullable=True, index=True)
    source_report_id = Column(UUID(as_uuid=True), ForeignKey("medical_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    insight_date = Column(Date, nullable=False, index=True)
    insight_kind = Column(String(50), nullable=False, index=True)
    confidence_tier = Column(String(20), nullable=False, default="low")
    association_label = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    possible_factors = Column(JSONB, nullable=False, default=list)
    evidence = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_correlation_insights_user_date", "user_id", "insight_date"),
    )


class NutritionTarget(Base):
    __tablename__ = "nutrition_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_date = Column(Date, nullable=False, index=True)
    calories_kcal = Column(Integer, nullable=False)
    protein_g = Column(Numeric(10, 2), nullable=False)
    carbohydrates_g = Column(Numeric(10, 2), nullable=False)
    fat_g = Column(Numeric(10, 2), nullable=False)
    fiber_g = Column(Numeric(10, 2), nullable=False)
    source = Column(String(30), nullable=False, default="calculated")
    calculation_basis = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_nutrition_targets_user_active", "user_id", "is_active"),
        Index("idx_nutrition_targets_user_target_date", "user_id", "target_date"),
    )
