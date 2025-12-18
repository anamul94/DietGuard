"""
Pagination response schemas for nutrition data.
"""

from pydantic import BaseModel, Field
from typing import List, Any, Optional
from datetime import datetime


class NutritionDataItem(BaseModel):
    """Single nutrition data item"""
    id: int = Field(..., description="Record ID")
    created_at: str = Field(..., description="Timestamp when the record was created (ISO format)")
    data: dict = Field(..., description="Nutrition data including food_analysis, meal_type, and timestamp")


class PaginatedNutritionResponse(BaseModel):
    """Paginated response for nutrition data"""
    items: List[NutritionDataItem] = Field(..., description="List of nutrition data items for the current page")
    total_count: int = Field(..., description="Total number of records matching the query")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 123,
                        "created_at": "2025-12-18T09:30:00+00:00",
                        "data": {
                            "food_analysis": {
                                "fooditems": ["pizza with cheese", "grilled chicken"],
                                "nutrition": {"calories": 650, "protein": "45g"}
                            },
                            "meal_type": "breakfast",
                            "timestamp": "2025-12-18T09:30:00+00:00"
                        }
                    }
                ],
                "total_count": 50,
                "page": 1,
                "page_size": 10,
                "total_pages": 5
            }
        }
