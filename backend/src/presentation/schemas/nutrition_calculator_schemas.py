"""
Nutrition calculation related Pydantic schemas.

Contains models for nutrition calculation requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List
from .food_schemas import NutritionInfo


class NutritionCalculationRequest(BaseModel):
    """Request model for nutrition calculation endpoint"""
    fooditems: List[str] = Field(
        ..., 
        description="List of food items with quantities (e.g., '1 grilled chicken with naan roti', '2 slices pizza with cheese and tomato')",
        min_length=1
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "fooditems": [
                    "1 grilled chicken with naan roti",
                    "2 slices pizza with cheese and tomato"
                ]
            }
        }


class NutritionCalculationResponse(BaseModel):
    """Response model for nutrition calculation endpoint"""
    fooditems: List[str] = Field(..., description="List of food items that were analyzed")
    nutrition: NutritionInfo = Field(..., description="Total nutritional information for all food items")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fooditems": [
                    "1 grilled chicken with naan roti",
                    "2 slices pizza with cheese and tomato"
                ],
                "nutrition": {
                    "calories": 650,
                    "protein": "45g",
                    "carbohydrates": "12g",
                    "fat": "48g",
                    "fiber": "1g",
                    "sugar": "8g"
                }
            }
        }
