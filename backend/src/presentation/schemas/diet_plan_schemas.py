from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DietPlanMealFood(BaseModel):
    name: str
    quantity: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float

class DietPlanMealSchema(BaseModel):
    day_of_week: int
    meal_type: str
    meal_name: str
    description: Optional[str] = None
    foods: List[DietPlanMealFood]
    total_calories: int
    total_protein_g: float
    notes: Optional[str] = None

class MacroTargets(BaseModel):
    calories_kcal: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    fiber_g: float

    class Config:
        json_schema_extra = {
            "example": {
                "calories_kcal": 2000,
                "protein_g": 120,
                "carbohydrates_g": 225,
                "fat_g": 70,
                "fiber_g": 30,
            }
        }


class DietPlanResponse(BaseModel):
    plan_id: str
    valid_from: date
    valid_until: date
    generated_by: str
    trigger: str
    calorie_target: int
    macro_targets: MacroTargets
    notes: Optional[str] = None
    is_active: bool
    meals: List[DietPlanMealSchema] = Field(default_factory=list)
