"""
Food-related Pydantic schemas.

Contains models for food items, nutritional information, and food analysis.
"""

from pydantic import BaseModel, Field
from pydantic import field_validator
from typing import Any, List

from ...infrastructure.utils.nutrition_utils import normalize_nutrition_metric


class FoodItem(BaseModel):
    """Model for individual food item"""
    name: str = Field(..., description="Name of the food item")
    quantity: str = Field(..., description="Quantity or serving size")
    preparation: str = Field(..., description="Preparation method or cooking style")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Chicken wings",
                "quantity": "8-10 pieces",
                "preparation": "Glazed/caramelized"
            }
        }


class NutritionMetric(BaseModel):
    """Model for a single nutrition metric with explicit units."""

    value: float = Field(..., description="Numeric nutrition value", ge=0)
    unit: str = Field(..., description="Unit for the nutrition value")

    class Config:
        json_schema_extra = {
            "example": {
                "value": 12,
                "unit": "g",
            }
        }


class NutritionInfo(BaseModel):
    """Model for nutritional information"""
    calories: NutritionMetric = Field(..., description="Total calories with value and unit")
    protein: NutritionMetric = Field(..., description="Protein content with value and unit")
    carbohydrates: NutritionMetric = Field(..., description="Carbohydrate content with value and unit")
    fat: NutritionMetric = Field(..., description="Fat content with value and unit")
    fiber: NutritionMetric = Field(..., description="Fiber content with value and unit")
    sugar: NutritionMetric = Field(..., description="Sugar content with value and unit")

    @field_validator("calories", mode="before")
    @classmethod
    def normalize_calories(cls, value: Any) -> Any:
        return normalize_nutrition_metric(value, "kcal")

    @field_validator("protein", "carbohydrates", "fat", "fiber", "sugar", mode="before")
    @classmethod
    def normalize_gram_metrics(cls, value: Any) -> Any:
        return normalize_nutrition_metric(value, "g")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calories": {"value": 650, "unit": "kcal"},
                "protein": {"value": 45, "unit": "g"},
                "carbohydrates": {"value": 12, "unit": "g"},
                "fat": {"value": 48, "unit": "g"},
                "fiber": {"value": 1, "unit": "g"},
                "sugar": {"value": 8, "unit": "g"}
            }
        }


class FoodNutritionBreakdownItem(BaseModel):
    """Item-level nutrition estimate for a single food item."""

    name: str = Field(..., description="Name of the food item")
    quantity: str | None = Field(None, description="Estimated quantity or serving size")
    preparation: str | None = Field(None, description="Preparation method if identifiable")
    nutrition: NutritionInfo = Field(..., description="Estimated nutrition for this individual item")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Pizza with cheese and tomato",
                "quantity": "2 slices",
                "preparation": "Baked",
                "nutrition": {
                    "calories": {"value": 320, "unit": "kcal"},
                    "protein": {"value": 12, "unit": "g"},
                    "carbohydrates": {"value": 38, "unit": "g"},
                    "fat": {"value": 14, "unit": "g"},
                    "fiber": {"value": 2, "unit": "g"},
                    "sugar": {"value": 4, "unit": "g"}
                }
            }
        }


class FoodAnalysis(BaseModel):
    """Structured model for food analysis"""
    fooditem_details: List[FoodNutritionBreakdownItem] = Field(
        default_factory=list,
        description="Per-item nutrition estimates for each identified food item",
    )
    nutrition: NutritionInfo = Field(..., description="Aggregated nutritional information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fooditem_details": [
                    {
                        "name": "pizza with cheese and tomato",
                        "quantity": "2 slices",
                        "preparation": "baked",
                        "nutrition": {
                            "calories": {"value": 320, "unit": "kcal"},
                            "protein": {"value": 12, "unit": "g"},
                            "carbohydrates": {"value": 38, "unit": "g"},
                            "fat": {"value": 14, "unit": "g"},
                            "fiber": {"value": 2, "unit": "g"},
                            "sugar": {"value": 4, "unit": "g"}
                        }
                    },
                    {
                        "name": "grilled chicken with naan roti",
                        "quantity": "1 plate",
                        "preparation": "grilled",
                        "nutrition": {
                            "calories": {"value": 330, "unit": "kcal"},
                            "protein": {"value": 33, "unit": "g"},
                            "carbohydrates": {"value": 20, "unit": "g"},
                            "fat": {"value": 12, "unit": "g"},
                            "fiber": {"value": 1, "unit": "g"},
                            "sugar": {"value": 2, "unit": "g"}
                        }
                    }
                ],
                "nutrition": {
                    "calories": {"value": 650, "unit": "kcal"},
                    "protein": {"value": 45, "unit": "g"},
                    "carbohydrates": {"value": 12, "unit": "g"},
                    "fat": {"value": 48, "unit": "g"},
                    "fiber": {"value": 1, "unit": "g"},
                    "sugar": {"value": 8, "unit": "g"}
                }
            }
        }


class FoodUploadResponse(BaseModel):
    """Response model for food upload endpoint"""
    user_email: str = Field(..., description="Email of the user who uploaded the food")
    files_processed: int = Field(..., description="Number of files processed", ge=1)
    filenames: List[str] = Field(..., description="List of uploaded filenames")
    food_analysis: FoodAnalysis = Field(..., description="AI-generated food analysis containing nutritional information and food identification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "files_processed": 1,
                "filenames": ["food_image.jpg"],
                "food_analysis": {
                    "fooditem_details": [
                        {
                            "name": "pizza with cheese and tomato",
                            "quantity": "2 slices",
                            "preparation": "baked",
                            "nutrition": {
                                "calories": {"value": 320, "unit": "kcal"},
                                "protein": {"value": 12, "unit": "g"},
                                "carbohydrates": {"value": 38, "unit": "g"},
                                "fat": {"value": 14, "unit": "g"},
                                "fiber": {"value": 2, "unit": "g"},
                                "sugar": {"value": 4, "unit": "g"}
                            }
                        }
                    ],
                    "nutrition": {
                        "calories": {"value": 650, "unit": "kcal"},
                        "protein": {"value": 45, "unit": "g"},
                        "carbohydrates": {"value": 12, "unit": "g"},
                        "fat": {"value": 48, "unit": "g"},
                        "fiber": {"value": 1, "unit": "g"},
                        "sugar": {"value": 8, "unit": "g"}
                    }
                }
            }
        }
