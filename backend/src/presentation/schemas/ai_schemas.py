"""
AI Agent Schemas for Swagger Documentation

This module contains Pydantic schemas for AI agent endpoints with proper
examples and descriptions for Swagger/OpenAPI documentation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class FoodUploadRequest(BaseModel):
    """Request model for food upload"""
    meal_type: str = Field(
        ...,
        description="Type of meal",
        example="lunch",
        pattern="^(breakfast|lunch|dinner|snack)$"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "meal_type": "lunch"
            }
        }


class FoodAnalysisResponse(BaseModel):
    """Response from food analysis AI agent"""
    meal_type: str = Field(..., description="Type of meal analyzed", example="lunch")
    files_processed: int = Field(..., description="Number of images processed", example=2)
    filenames: List[str] = Field(
        ...,
        description="List of uploaded filenames",
        example=["burger.jpg", "fries.jpg"]
    )
    food_analysis: str = Field(
        ...,
        description="Detailed food analysis in markdown format",
        example="""## Food Analysis

**Detected Items:**
- Cheeseburger with lettuce, tomato, and pickles
- French fries (medium portion)
- Soft drink (cola)

**Nutritional Estimate:**
- **Total Calories:** ~850 kcal
- **Protein:** 25g
- **Carbohydrates:** 90g
- **Fat:** 35g
- **Sodium:** 1200mg

**Health Assessment:**
This meal is high in calories, saturated fat, and sodium. Consider:
- Choosing grilled chicken instead of beef
- Replacing fries with a side salad
- Opting for water or unsweetened beverages

**Recommendations:**
- Add more vegetables
- Control portion sizes
- Balance with lighter meals throughout the day"""
    )
    
    class Config:
        schema_extra = {
            "example": {
                "meal_type": "lunch",
                "files_processed": 2,
                "filenames": ["burger.jpg", "fries.jpg"],
                "food_analysis": "## Food Analysis\n\n**Detected Items:**\n- Cheeseburger\n- French fries\n\n**Nutritional Estimate:**\n- Calories: 850 kcal\n- Protein: 25g\n- Carbs: 90g\n- Fat: 35g"
            }
        }


class ReportUploadResponse(BaseModel):
    """Response from medical report analysis"""
    files_processed: int = Field(..., description="Number of reports processed", example=2)
    filenames: List[str] = Field(
        ...,
        description="List of uploaded report filenames",
        example=["blood_test.pdf", "cholesterol_report.pdf"]
    )
    individual_analyses: List[Dict[str, str]] = Field(
        ...,
        description="Individual analysis for each report",
        example=[
            {
                "filename": "blood_test.pdf",
                "analysis": "## Blood Test Analysis\n\n**Key Findings:**\n- Hemoglobin: 14.5 g/dL (Normal)\n- White Blood Cells: 7,200/μL (Normal)\n- Glucose: 105 mg/dL (Slightly elevated)"
            },
            {
                "filename": "cholesterol_report.pdf",
                "analysis": "## Cholesterol Report\n\n**Lipid Profile:**\n- Total Cholesterol: 210 mg/dL (Borderline high)\n- LDL: 140 mg/dL (High)\n- HDL: 45 mg/dL (Low)\n- Triglycerides: 150 mg/dL (Normal)"
            }
        ]
    )
    combined_summary: str = Field(
        ...,
        description="Combined summary of all reports",
        example="""## Overall Health Summary

**Key Findings:**
1. Blood glucose slightly elevated - monitor for pre-diabetes
2. Cholesterol levels need attention - LDL is high, HDL is low
3. Overall blood count is normal

**Recommendations:**
1. Dietary changes to lower cholesterol
2. Increase physical activity
3. Monitor blood sugar levels
4. Follow up with healthcare provider in 3 months"""
    )
    
    class Config:
        schema_extra = {
            "example": {
                "files_processed": 2,
                "filenames": ["blood_test.pdf", "cholesterol_report.pdf"],
                "individual_analyses": [
                    {
                        "filename": "blood_test.pdf",
                        "analysis": "Blood test shows normal hemoglobin and WBC count. Glucose slightly elevated at 105 mg/dL."
                    }
                ],
                "combined_summary": "Overall health is good. Monitor glucose levels and consider lifestyle modifications for cholesterol management."
            }
        }


class NutritionAdviceRequest(BaseModel):
    """Request for nutrition advice from AI"""
    query: str = Field(
        ...,
        description="User's nutrition question",
        example="What should I eat for breakfast to lose weight?",
        min_length=10,
        max_length=500
    )
    context: Optional[str] = Field(
        None,
        description="Additional context about user's health or goals",
        example="I'm 30 years old, weight 80kg, height 175cm, and want to lose 5kg in 2 months",
        max_length=1000
    )
    
    class Config:
        schema_extra = {
            "example": {
                "query": "What should I eat for breakfast to lose weight?",
                "context": "I'm 30 years old, weight 80kg, and want to lose 5kg"
            }
        }


class NutritionAdviceResponse(BaseModel):
    """Response from nutrition advice AI"""
    advice: str = Field(
        ...,
        description="Detailed nutrition advice in markdown format",
        example="""## Breakfast Recommendations for Weight Loss

**Ideal Breakfast Components:**

1. **Protein-Rich Foods (25-30g protein):**
   - Greek yogurt (200g) - 20g protein
   - 2 eggs - 12g protein
   - Protein smoothie with whey protein

2. **Complex Carbohydrates:**
   - Oatmeal (40g dry) - 150 calories
   - Whole grain toast (1 slice)
   - Quinoa porridge

3. **Healthy Fats:**
   - Avocado (1/4) - 80 calories
   - Nuts (15g) - 90 calories
   - Chia seeds (1 tbsp)

4. **Fiber & Vegetables:**
   - Berries (100g)
   - Spinach or kale
   - Tomatoes

**Sample Breakfast (400-450 calories):**
- Greek yogurt (200g) with berries
- 1 slice whole grain toast with avocado
- Green tea or black coffee

**Tips:**
- Eat within 1 hour of waking
- Drink 500ml water before breakfast
- Avoid sugary cereals and pastries
- Aim for 400-500 calories"""
    )
    recommendations: List[str] = Field(
        ...,
        description="List of specific recommendations",
        example=[
            "Eat protein-rich breakfast within 1 hour of waking",
            "Include 25-30g of protein in your breakfast",
            "Choose complex carbohydrates over simple sugars",
            "Add vegetables or fruits for fiber",
            "Stay hydrated with water or green tea",
            "Avoid processed foods and sugary drinks"
        ]
    )
    
    class Config:
        schema_extra = {
            "example": {
                "advice": "## Breakfast for Weight Loss\n\nFocus on protein-rich foods like eggs, Greek yogurt, and lean meats. Include complex carbs like oatmeal and whole grain toast. Add healthy fats from avocado or nuts.",
                "recommendations": [
                    "Eat 25-30g protein at breakfast",
                    "Choose whole grains over refined carbs",
                    "Include vegetables or fruits",
                    "Drink water before eating"
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message", example="Invalid meal type. Must be one of: breakfast, lunch, dinner, snack")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Authentication required. Please provide a valid JWT token."
            }
        }


class SubscriptionLimitError(BaseModel):
    """Error when subscription limit is reached"""
    detail: str = Field(..., description="Error message")
    limit_type: str = Field(..., description="Type of limit reached", example="daily_upload_limit")
    current_usage: int = Field(..., description="Current usage count", example=20)
    limit: int = Field(..., description="Maximum allowed", example=20)
    reset_time: Optional[datetime] = Field(None, description="When the limit resets")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Daily upload limit reached. Upgrade your subscription for more uploads.",
                "limit_type": "daily_upload_limit",
                "current_usage": 20,
                "limit": 20,
                "reset_time": "2025-12-18T00:00:00Z"
            }
        }
