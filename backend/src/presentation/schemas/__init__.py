"""
Presentation layer schemas package.

This package contains all Pydantic models for API request/response validation.
Organized by domain for better maintainability.
"""

from .food_schemas import (
    FoodItem,
    FoodNutritionBreakdownItem,
    NutritionInfo,
    NutritionMetric,
    FoodAnalysis,
    FoodUploadResponse,
)

from .nutrition_schemas import (
    NutritionAdviceRequest,
    NutritionAdviceResponse,
)

from .ai_schemas import (
    FoodUploadRequest,
    FoodAnalysisResponse,
    ReportUploadResponse,
    ErrorResponse,
    SubscriptionLimitError,
)

from .nutrition_calculator_schemas import (
    NutritionCalculationRequest,
    NutritionCalculationResponse,
)

from .ingredient_schemas import (
    DietaryFlags,
    IngredientDetail,
    IngredientAnalysis,
    IngredientScanResponse,
)
from .health_schemas import (
    AdherenceMetricResponse,
    ConditionSnapshotResponse,
    CorrelationInsightResponse,
    DeviceVitalSyncRequest,
    MealConfirmRequest,
    MealConfirmResponse,
    MealDraftItem,
    MealDraftResponse,
    NutritionTargetAdherenceResponse,
    NutritionTargetManualCreateRequest,
    NutritionTargetResponse,
    PeriodInsightsResponse,
    StructuredHealthProfileResponse,
    StructuredReportEntity,
    StructuredReportSection,
    VitalBatchCreate,
    VitalBatchResponse,
    VitalEntryCreate,
    VitalEntryResponse,
)


__all__ = [
    # Food schemas
    "FoodItem",
    "FoodNutritionBreakdownItem",
    "NutritionInfo",
    "NutritionMetric",
    "FoodAnalysis",
    "FoodUploadResponse",
    # Nutrition schemas
    "NutritionAdviceRequest",
    "NutritionAdviceResponse",
    # AI Agent schemas
    "FoodUploadRequest",
    "FoodAnalysisResponse",
    "ReportUploadResponse",
    "ErrorResponse",
    "SubscriptionLimitError",
    # Nutrition Calculator schemas
    "NutritionCalculationRequest",
    "NutritionCalculationResponse",
    # Ingredient Scanner schemas
    "AllergenInfo",
    "DietaryFlags",
    "IngredientDetail",
    "IngredientAnalysis",
    "IngredientScanResponse",
    # Health timeline schemas
    "ConditionSnapshotResponse",
    "CorrelationInsightResponse",
    "DeviceVitalSyncRequest",
    "MealConfirmRequest",
    "MealConfirmResponse",
    "MealDraftItem",
    "MealDraftResponse",
    "NutritionTargetAdherenceResponse",
    "NutritionTargetManualCreateRequest",
    "NutritionTargetResponse",
    "AdherenceMetricResponse",
    "PeriodInsightsResponse",
    "StructuredHealthProfileResponse",
    "StructuredReportEntity",
    "StructuredReportSection",
    "VitalBatchCreate",
    "VitalBatchResponse",
    "VitalEntryCreate",
    "VitalEntryResponse",
]
