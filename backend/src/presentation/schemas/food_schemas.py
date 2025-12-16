"""
Food-related Pydantic schemas.

Contains models for food items, nutritional information, and food analysis.
"""

from pydantic import BaseModel, Field
from typing import List


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


class NutritionInfo(BaseModel):
    """Model for nutritional information"""
    calories: int = Field(..., description="Total calories", ge=0)
    protein: str = Field(..., description="Protein content (e.g., '45g')")
    carbohydrates: str = Field(..., description="Carbohydrate content (e.g., '12g')")
    fat: str = Field(..., description="Fat content (e.g., '48g')")
    fiber: str = Field(..., description="Fiber content (e.g., '1g')")
    sugar: str = Field(..., description="Sugar content (e.g., '8g')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calories": 650,
                "protein": "45g",
                "carbohydrates": "12g",
                "fat": "48g",
                "fiber": "1g",
                "sugar": "8g"
            }
        }


class FoodAnalysis(BaseModel):
    """Structured model for food analysis"""
    food_items: List[FoodItem] = Field(..., description="List of identified food items")
    nutrition: NutritionInfo = Field(..., description="Aggregated nutritional information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "food_items": [
                    {
                        "name": "Chicken wings",
                        "quantity": "8-10 pieces",
                        "preparation": "Glazed/caramelized"
                    },
                    {
                        "name": "Green onions",
                        "quantity": "2 tablespoons",
                        "preparation": "Chopped, garnish"
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
                    "food_items": [
                        {
                            "name": "Chicken wings",
                            "quantity": "8-10 pieces",
                            "preparation": "Glazed/caramelized"
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
                }
            }
        }
