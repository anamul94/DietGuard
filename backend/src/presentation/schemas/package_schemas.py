"""
Pydantic schemas for subscription packages.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from decimal import Decimal


class PackageBase(BaseModel):
    """Base package schema"""
    name: str = Field(..., description="Package name", example="Monthly")
    price: Decimal = Field(..., description="Package price", example=10.00)
    billing_period: str = Field(..., description="Billing period", example="monthly")
    daily_upload_limit: int = Field(..., description="Daily upload limit", example=20)
    daily_nutrition_limit: int = Field(..., description="Daily nutrition query limit", example=20)
    features: Optional[Dict[str, Any]] = Field(None, description="Package features")
    is_active: bool = Field(True, description="Whether package is active")


class PackageCreate(PackageBase):
    """Schema for creating a package"""
    pass


class PackageUpdate(BaseModel):
    """Schema for updating a package"""
    name: Optional[str] = None
    price: Optional[Decimal] = None
    billing_period: Optional[str] = None
    daily_upload_limit: Optional[int] = None
    daily_nutrition_limit: Optional[int] = None
    features: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PackageResponse(PackageBase):
    """Schema for package response"""
    id: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Monthly",
                "price": 10.00,
                "billing_period": "monthly",
                "daily_upload_limit": 20,
                "daily_nutrition_limit": 20,
                "features": {
                    "food_analysis": True,
                    "nutrition_advice": True,
                    "priority_support": True
                },
                "is_active": True,
                "created_at": "2025-12-16T10:00:00Z",
                "updated_at": "2025-12-16T10:00:00Z"
            }
        }
