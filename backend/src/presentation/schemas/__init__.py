"""
Presentation layer schemas package.

This package contains all Pydantic models for API request/response validation.
Organized by domain for better maintainability.
"""

from .food_schemas import (
    FoodItem,
    NutritionInfo,
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

__all__ = [
    # Food schemas
    "FoodItem",
    "NutritionInfo",
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
]
