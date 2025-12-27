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
                    "fooditems": ["1 grilled chicken", "1 naan roti"],
                    "nutrition": {
                        "calories": 450,
                        "protein": "35g",
                        "carbohydrates": "40g",
                        "fat": "15g",
                        "fiber": "3g",
                        "sugar": "2g"
                    }
                }
            }
        }



class NutritionCalculationResponse(BaseModel):
    """Response model for nutrition calculation endpoint"""
    food_analysis: FoodAnalysis = Field(..., description="Food analysis containing food items and nutrition data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "food_analysis": {
                    "fooditems": [
                        "Steamed white rice",
                        "Yellow lentil dal soup",
                        "Mixed vegetable curry with potatoes and other vegetables",
                        "Sautéed leafy greens (likely spinach)",
                        "Pickled vegetables (likely cucumber or gourd)",
                        "Brown spiced chutney (likely tamarind based)",
                        "Plain yogurt",
                        "Sliced orange or mango fruit"
                    ],
                    "nutrition": {
                        "calories": 650,
                        "protein": "22g",
                        "carbohydrates": "105g",
                        "fat": "15g",
                        "fiber": "12g",
                        "sugar": "18g"
                    }
                }
            }
        }
