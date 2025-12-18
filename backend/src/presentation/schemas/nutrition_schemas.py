"""
Nutrition advice-related Pydantic schemas.

Contains models for nutrition analysis requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from .food_schemas import FoodAnalysis


class NutritionAdviceRequest(BaseModel):
    """Request model for nutrition advice endpoint"""
    food_analysis: FoodAnalysis = Field(
        ..., 
        description="Structured food analysis object returned from /upload-food endpoint"
    )
    meal_type: str = Field(
        ..., 
        description="Type of meal",
        pattern="^(breakfast|lunch|dinner|snack)$"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "food_analysis": {
                    "fooditems": [
                        "pizza with cheese and tomato",
                        "grilled chicken with naan roti"
                    ],
                    "nutrition": {
                        "calories": 650,
                        "protein": "45g",
                        "carbohydrates": "12g",
                        "fat": "48g",
                        "fiber": "1g",
                        "sugar": "8g"
                    }
                },
                "meal_type": "breakfast"
            }
        }


class NutritionAdviceResponse(BaseModel):
    """Response model for nutrition advice endpoint"""
    user_email: str = Field(..., description="Email of the user")
    meal_type: str = Field(..., description="Meal type for which advice was generated")
    nutritionist_recommendations: str = Field(
        ..., 
        description="AI-generated nutritionist recommendations based on food analysis and user profile"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "meal_type": "breakfast",
                "nutritionist_recommendations": "This meal provides good protein content. Consider adding vegetables for fiber..."
            }
        }
