"""
Schemas for structured health timeline endpoints.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .food_schemas import FoodAnalysis

from pydantic import BaseModel, Field, field_validator


class StructuredLabResult(BaseModel):
    report_category: Optional[str] = None
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
    report_category: Optional[str] = None
    medication_name: str
    dosage: Optional[str] = None
    schedule: Optional[str] = None
    timing_notes: Optional[str] = None
    with_food: Optional[bool] = None


class StructuredReportEntity(BaseModel):
    report_category: Optional[str] = None
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


class StructuredReportMetadata(BaseModel):
    report_id: Optional[str] = None
    version: Optional[int] = None
    report_date: Optional[str] = None
    summary: Optional[str] = None
    filenames: List[str] = Field(default_factory=list)
    report_category: Optional[str] = None
    document_type: Optional[str] = None
    title: Optional[str] = None
    parser_version: Optional[str] = None
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)


class StructuredHealthProfileResponse(BaseModel):
    report: StructuredReportMetadata
    current_reports: List[StructuredReportMetadata] = Field(default_factory=list)
    snapshot: ConditionSnapshotResponse
    labs: List[StructuredLabResult]
    medications: List[StructuredMedication]
    entities: List[StructuredReportEntity] = Field(default_factory=list)
    sections: List[StructuredReportSection] = Field(default_factory=list)
    unmapped_entities: List[StructuredReportEntity] = Field(default_factory=list)
    lab_trends: List[Dict[str, Any]]
    active_categories: List[str] = Field(default_factory=list)
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


class MealConfirmRequest(BaseModel):
    meal_type: str = Field(..., pattern="^(breakfast|lunch|dinner|snack)$")
    meal_time: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    meal_date: date
    food_analysis: FoodAnalysis = Field(
        ...,
        description="Full food analysis payload (per-item nutrition + totals) just like the agent returns.",
        example={
            "fooditem_details": [
                {
                    "name": "Grilled Chicken Salad",
                    "quantity": "100g",
                    "preparation": "grilled",
                    "nutrition": {
                        "calories": {"value": 320, "unit": "kcal"},
                        "protein": {"value": 31, "unit": "g"},
                        "carbohydrates": {"value": 5, "unit": "g"},
                        "fat": {"value": 12, "unit": "g"},
                        "fiber": {"value": 4, "unit": "g"},
                        "sugar": {"value": 2, "unit": "g"}
                    }
                }
            ],
            "nutrition": {
                "calories": {"value": 650, "unit": "kcal"},
                "protein": {"value": 45, "unit": "g"},
                "carbohydrates": {"value": 60, "unit": "g"},
                "fat": {"value": 18, "unit": "g"},
                "fiber": {"value": 10, "unit": "g"},
                "sugar": {"value": 6, "unit": "g"}
            }
        },
    )

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
    food_analysis: FoodAnalysis
    source_filenames: List[str] = Field(default_factory=list)


class MealNutritionMetricResponse(BaseModel):
    value: float
    unit: str


class MealNutritionTotalsResponse(BaseModel):
    calories: MealNutritionMetricResponse
    protein: MealNutritionMetricResponse
    carbohydrates: MealNutritionMetricResponse
    fat: MealNutritionMetricResponse
    fiber: MealNutritionMetricResponse
    sugar: MealNutritionMetricResponse


class MealHistoryItemResponse(BaseModel):
    name: str
    quantity: Optional[str] = None
    role: str
    preparation: Optional[str] = None
    source_label: Optional[str] = None
    confidence: Optional[float] = None


class TodayMealNutritionSummaryResponse(BaseModel):
    date: str
    meal_count: int
    nutrition_totals: MealNutritionTotalsResponse


class MealHistoryEntryResponse(BaseModel):
    meal_event_id: str
    meal_type: str
    meal_date: str
    meal_time: str
    source: str
    notes: Optional[str] = None
    food_names: List[str] = Field(default_factory=list)
    items: List[MealHistoryItemResponse] = Field(default_factory=list)
    source_filenames: List[str] = Field(default_factory=list)
    nutrition_totals: MealNutritionTotalsResponse
    food_analysis: Dict[str, Any]


class PaginatedMealHistoryResponse(BaseModel):
    items: List[MealHistoryEntryResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


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


class NutritionTargetResponse(BaseModel):
    target_id: str
    target_date: str
    calories_kcal: int
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    fiber_g: float
    source: str
    calculation_basis: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: Optional[str] = None


class NutritionTargetManualCreateRequest(BaseModel):
    target_date: date
    calories_kcal: int = Field(..., ge=800, le=6000)
    protein_g: float = Field(..., ge=0, le=500)
    carbohydrates_g: float = Field(..., ge=0, le=1000)
    fat_g: float = Field(..., ge=0, le=300)
    fiber_g: float = Field(..., ge=0, le=150)


class AdherenceMetricResponse(BaseModel):
    percent: Optional[float] = None
    status: str


class NutritionTargetAdherenceResponse(BaseModel):
    date: str
    target: NutritionTargetResponse
    intake: Dict[str, float | int]
    adherence: Dict[str, AdherenceMetricResponse]
    generated_at: str
