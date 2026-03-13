"""
Schemas for structured health timeline endpoints.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class StructuredLabResult(BaseModel):
    test_name: str
    canonical_name: Optional[str] = None
    value_text: str
    value_numeric: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None
    abnormal_flag: Optional[str] = None
    lab_date: Optional[str] = None


class StructuredMedication(BaseModel):
    medication_name: str
    dosage: Optional[str] = None
    schedule: Optional[str] = None
    timing_notes: Optional[str] = None
    with_food: Optional[bool] = None


class StructuredReportEntity(BaseModel):
    entity_type: str
    category: Optional[str] = None
    label: str
    canonical_name: Optional[str] = None
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[str] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    page_number: Optional[int] = None
    confidence: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class StructuredReportSection(BaseModel):
    name: str
    kind: str
    summary: Optional[str] = None
    page_number: Optional[int] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ConditionSnapshotResponse(BaseModel):
    diabetes_status: str
    hypertension_status: str
    kidney_disease_stage: Optional[str] = None
    dyslipidemia_status: str
    food_restrictions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    dietary_preferences: List[str] = Field(default_factory=list)
    doctor_advice: List[str] = Field(default_factory=list)
    extra_conditions: List[str] = Field(default_factory=list)


class StructuredHealthProfileResponse(BaseModel):
    report: Dict[str, Any]
    snapshot: ConditionSnapshotResponse
    labs: List[StructuredLabResult]
    medications: List[StructuredMedication]
    entities: List[StructuredReportEntity] = Field(default_factory=list)
    sections: List[StructuredReportSection] = Field(default_factory=list)
    unmapped_entities: List[StructuredReportEntity] = Field(default_factory=list)
    lab_trends: List[Dict[str, Any]]
    health_context_summary: str


class MealDraftItem(BaseModel):
    name: str
    quantity: Optional[str] = None
    role: str = "main"
    preparation: Optional[str] = None
    source_label: Optional[str] = None
    confidence: Optional[float] = None
    editable: bool = True


class MealDraftResponse(BaseModel):
    meal_title: str
    items: List[MealDraftItem]
    warnings: List[str] = Field(default_factory=list)
    filenames: List[str] = Field(default_factory=list)
    raw_food_analysis: Dict[str, Any]


class ConfirmedMealItemInput(BaseModel):
    name: str
    quantity: Optional[str] = None
    role: str = Field(default="main", pattern="^(main|side|condiment|beverage)$")
    preparation: Optional[str] = None
    source_label: Optional[str] = None
    confidence: Optional[float] = None


class MealConfirmRequest(BaseModel):
    meal_type: str = Field(..., pattern="^(breakfast|lunch|dinner|snack)$")
    meal_time: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    meal_date: date
    items: List[ConfirmedMealItemInput]
    source_filenames: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("meal_date")
    @classmethod
    def validate_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("meal_date cannot be in the future")
        return value


class MealConfirmResponse(BaseModel):
    meal_event_id: str
    meal_type: str
    meal_date: str
    meal_time: str
    food_analysis: Dict[str, Any]
    source_filenames: List[str] = Field(default_factory=list)


class VitalEntryCreate(BaseModel):
    vital_type: str
    value_primary: float
    value_secondary: Optional[float] = None
    unit: str
    captured_at: datetime
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_device: Optional[str] = None


class VitalBatchCreate(BaseModel):
    entries: List[VitalEntryCreate]


class DeviceVitalSyncRequest(VitalBatchCreate):
    source_device: str


class VitalEntryResponse(BaseModel):
    vital_type: str
    value_primary: float
    value_secondary: Optional[float] = None
    unit: str
    captured_at: datetime
    source: str
    source_device: Optional[str] = None


class VitalBatchResponse(BaseModel):
    created_count: int
    source: str
    entries: List[VitalEntryResponse]


class CorrelationInsightResponse(BaseModel):
    meal_id: str
    vital_id: str
    meal_time: str
    vital_time: str
    vital_type: str
    confidence_tier: str
    association_label: str
    explanation: str
    possible_factors: List[str]
    evidence: Dict[str, Any]


class PeriodInsightsResponse(BaseModel):
    period_start: str
    period_end: str
    meal_count: int
    vital_count: int
    mood_checkin_count: int
    nutrition_totals: Dict[str, Any]
    vital_overview: List[Dict[str, Any]]
    associations: List[CorrelationInsightResponse]
    narrative: str
    possible_factors: List[str]
