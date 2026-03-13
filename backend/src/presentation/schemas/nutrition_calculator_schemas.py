"""
Nutrition calculation related Pydantic schemas.

Contains models for nutrition calculation requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .food_schemas import NutritionInfo, FoodAnalysis


class NutritionCalculationRequest(BaseModel):
    """Request model for nutrition calculation endpoint"""
    fooditems: List[str] = Field(
        ..., 
        description="List of food items with quantities (e.g., '1 grilled chicken with naan roti', '2 slices pizza with cheese and tomato')",
        min_length=1
    )
    old_food_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Previous food analysis with nutrition values for reference to maintain calculation consistency"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "fooditems": [
                    "1 grilled chicken with naan roti",
                    "2 slices pizza with cheese and tomato"
                ],
                "old_food_analysis": {
                    "fooditem_details": [
                        {
                            "name": "grilled chicken",
                            "quantity": "1 serving",
                            "nutrition": {
                                "calories": {"value": 320, "unit": "kcal"},
                                "protein": {"value": 30, "unit": "g"},
                                "carbohydrates": {"value": 0, "unit": "g"},
                                "fat": {"value": 14, "unit": "g"},
                                "fiber": {"value": 0, "unit": "g"},
                                "sugar": {"value": 0, "unit": "g"}
                            }
                        },
                        {
                            "name": "naan roti",
                            "quantity": "1 piece",
                            "nutrition": {
                                "calories": {"value": 130, "unit": "kcal"},
                                "protein": {"value": 5, "unit": "g"},
                                "carbohydrates": {"value": 27, "unit": "g"},
                                "fat": {"value": 1, "unit": "g"},
                                "fiber": {"value": 3, "unit": "g"},
                                "sugar": {"value": 2, "unit": "g"}
                            }
                        }
                    ],
                    "nutrition": {
                        "calories": {"value": 450, "unit": "kcal"},
                        "protein": {"value": 35, "unit": "g"},
                        "carbohydrates": {"value": 40, "unit": "g"},
                        "fat": {"value": 15, "unit": "g"},
                        "fiber": {"value": 3, "unit": "g"},
                        "sugar": {"value": 2, "unit": "g"}
                    }
                }
            }
        }



class NutritionCalculationResponse(BaseModel):
    """Response model for nutrition calculation endpoint"""
    food_analysis: FoodAnalysis = Field(..., description="Food analysis containing per-item and total nutrition data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "food_analysis": {
                    "fooditem_details": [
                        {
                            "name": "Steamed white rice",
                            "quantity": "1 bowl",
                            "preparation": "steamed",
                            "nutrition": {
                                "calories": {"value": 205, "unit": "kcal"},
                                "protein": {"value": 4, "unit": "g"},
                                "carbohydrates": {"value": 45, "unit": "g"},
                                "fat": {"value": 0.4, "unit": "g"},
                                "fiber": {"value": 0.6, "unit": "g"},
                                "sugar": {"value": 0.1, "unit": "g"}
                            }
                        }
                    ],
                    "nutrition": {
                        "calories": {"value": 650, "unit": "kcal"},
                        "protein": {"value": 22, "unit": "g"},
                        "carbohydrates": {"value": 105, "unit": "g"},
                        "fat": {"value": 15, "unit": "g"},
                        "fiber": {"value": 12, "unit": "g"},
                        "sugar": {"value": 18, "unit": "g"}
                    }
                }
            }
        }
