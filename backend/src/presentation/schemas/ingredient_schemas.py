"""
Ingredient scanning schemas for food packaging analysis.

Contains models for ingredient health analysis with color-coded ratings,
allergen information, and dietary compatibility flags.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class DietaryFlags(BaseModel):
    """Dietary compatibility flags"""
    vegan: bool = Field(..., description="Suitable for vegan diet")
    vegetarian: bool = Field(..., description="Suitable for vegetarian diet")
    halal: bool = Field(..., description="Halal certified or suitable")
    kosher: bool = Field(..., description="Kosher certified or suitable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vegan": True,
                "vegetarian": True,
                "halal": True,
                "kosher": True
            }
        }


class IngredientDetail(BaseModel):
    """Detailed analysis of a single ingredient"""
    name: str = Field(..., description="Ingredient name (including common name if chemical)")
    chemical_name: Optional[str] = Field(None, description="Chemical or technical name if applicable")
    common_name: Optional[str] = Field(None, description="Common/layman name for the ingredient")
    health_rating: str = Field(..., description="Health rating: 'green' (safe/healthy), 'yellow' (moderate concern), 'red' (harmful/avoid)")
    short_explanation: str = Field(..., description="Brief 1-2 sentence explanation in simple language")
    detailed_explanation: str = Field(..., description="Comprehensive explanation of health effects, usage, and concerns")
    concerns: List[str] = Field(default_factory=list, description="Specific health concerns or warnings")
    age_restrictions: Optional[str] = Field(None, description="Age-specific warnings or restrictions")
    dietary_flags: DietaryFlags = Field(..., description="Dietary compatibility information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Monosodium Glutamate (MSG / E621)",
                "chemical_name": "Monosodium Glutamate",
                "common_name": "MSG",
                "health_rating": "yellow",
                "short_explanation": "A flavor enhancer that may cause headaches in sensitive individuals.",
                "detailed_explanation": "MSG is a common flavor enhancer used to intensify savory tastes. While generally recognized as safe by food authorities, some people report sensitivity symptoms like headaches, flushing, or sweating. Not recommended in large amounts for young children.",
                "concerns": ["May cause headaches", "Not recommended for children under 5"],
                "age_restrictions": "Not recommended for children under 5 years",
                "dietary_flags": {
                    "vegan": True,
                    "vegetarian": True,
                    "halal": True,
                    "kosher": True
                }
            }
        }


class IngredientAnalysis(BaseModel):
    """Complete ingredient analysis from food packaging"""
    ingredients: List[IngredientDetail] = Field(..., description="List of analyzed ingredients with health ratings")
    overall_rating: str = Field(..., description="Overall product health rating: 'green', 'yellow', or 'red'")
    summary: str = Field(..., description="Product-level health summary in simple language")
    critical_warnings: List[str] = Field(default_factory=list, description="High-priority warnings (preservatives for children, allergens, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ingredients": [
                    {
                        "name": "Monosodium Glutamate (MSG / E621)",
                        "chemical_name": "Monosodium Glutamate",
                        "common_name": "MSG",
                        "health_rating": "yellow",
                        "short_explanation": "A flavor enhancer that may cause headaches.",
                        "detailed_explanation": "MSG is a flavor enhancer. Some people are sensitive to it.",
                        "concerns": ["May cause headaches"],
                        "age_restrictions": "Not recommended for children under 5",
                        "dietary_flags": {
                            "vegan": True,
                            "vegetarian": True,
                            "halal": True,
                            "kosher": True
                        }
                    }
                ],
                "overall_rating": "yellow",
                "summary": "This product contains flavor enhancers that may not be suitable for young children.",
                "critical_warnings": ["Contains MSG - not recommended for children under 5"]
            }
        }


class IngredientScanResponse(BaseModel):
    """Response model for ingredient scan endpoint"""
    user_email: str = Field(..., description="Email of the user who uploaded the image")
    filename: str = Field(..., description="Uploaded image filename")
    ingredient_analysis: IngredientAnalysis = Field(..., description="AI-generated ingredient analysis with health ratings")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "filename": "chips_label.jpg",
                "ingredient_analysis": {
                    "ingredients": [],
                    "overall_rating": "yellow",
                    "summary": "Product contains some ingredients of concern.",
                    "critical_warnings": []
                }
            }
        }
