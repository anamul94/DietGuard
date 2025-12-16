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
        description="Structured food analysis object returned from /upload_food/ endpoint"
    )
    meal_type: str = Field(
        ..., 
        description="Type of meal",
        pattern="^(breakfast|lunch|dinner|snack)$"
    )
    age: int = Field(
        ..., 
        description="User's age in years",
        ge=1,
        le=150
    )
    gender: str = Field(
        ..., 
        description="User's gender",
        pattern="^(male|female|other)$"
    )
    weight: float = Field(
        ...,
        description="User's weight in kg",
        ge=20,
        le=300
    )
    height: float = Field(
        ...,
        description="User's height in cm",
        ge=50,
        le=250
    )
    medical_report: Optional[str] = Field(
        None, 
        description="Optional medical report or health conditions. If not provided, nutritionist will give general advice."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "food_analysis": {
                    "food_items": [
                        {
                            "name": "Chicken wings",
                            "quantity": "8-10 pieces",
                            "preparation": "Glazed/caramelized"
                        },
                        {
                            "name": "Sesame seeds",
                            "quantity": "1 teaspoon",
                            "preparation": "Toasted, garnish"
                        }
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
                "age": 25,
                "gender": "male",
                "weight": 75.5,
                "height": 180.0,
                "medical_report": "No known allergies"
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
