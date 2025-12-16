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

__all__ = [
    # Food schemas
    "FoodItem",
    "NutritionInfo",
    "FoodAnalysis",
    "FoodUploadResponse",
    # Nutrition schemas
    "NutritionAdviceRequest",
    "NutritionAdviceResponse",
]
