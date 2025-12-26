"""
Nutrition advice-related Pydantic schemas.

Contains models for nutrition analysis requests and responses.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
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
    meal_time: str = Field(
        ...,
        description="Time when meal was consumed (HH:MM format, 24-hour)",
        pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    meal_date: Optional[date] = Field(
        None,
        description="Date of the meal (defaults to today if not provided)"
    )
    
    @field_validator('meal_date')
    @classmethod
    def validate_meal_date(cls, v):
        if v and v > date.today():
            raise ValueError('Meal date cannot be in the future')
        return v
    
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
                "meal_type": "breakfast",
                "meal_time": "09:00",
                "meal_date": "2025-12-26"
            }
        }


class MealInfo(BaseModel):
    """Meal timing information"""
    meal_time: str = Field(..., description="Time when meal was consumed (HH:MM)")
    meal_date: str = Field(..., description="Date of the meal (YYYY-MM-DD)")


class NutritionAdviceResponse(BaseModel):
    """Response model for nutrition advice endpoint"""
    user_email: str = Field(..., description="Email of the user")
    meal_type: str = Field(..., description="Meal type for which advice was generated")
    meal_info: Optional[MealInfo] = Field(None, description="Meal timing information")
    nutritionist_recommendations: str = Field(
        ..., 
        description="AI-generated nutritionist recommendations based on food analysis and user profile"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "meal_type": "breakfast",
                "meal_info": {
                    "meal_time": "09:00",
                    "meal_date": "2025-12-26"
                },
                "nutritionist_recommendations": "This meal provides good protein content. Consider adding vegetables for fiber..."
            }
        }
