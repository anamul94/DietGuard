from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngredientSchema(BaseModel):
    name: str = Field(description="Ingredient name")
    quantity: str = Field(description="Quantity with unit (e.g., '2 cups', '500g')")
    notes: Optional[str] = Field(default=None, description="Optional notes about the ingredient")


class InstructionStepSchema(BaseModel):
    step_number: int = Field(description="Step number in the cooking process")
    instruction: str = Field(description="Detailed instruction for this step")


class NutritionSchema(BaseModel):
    calories: int = Field(description="Calories per serving")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Carbohydrates in grams")
    fat_g: float = Field(description="Fat in grams")
    fiber_g: Optional[float] = Field(default=None, description="Fiber in grams")
    sodium_mg: Optional[float] = Field(default=None, description="Sodium in milligrams")
    sugar_g: Optional[float] = Field(default=None, description="Sugar in grams")


class RecipeSchema(BaseModel):
    recipe_name: str = Field(description="Name of the recipe")
    cuisine: str = Field(description="Cuisine type (Indian, Italian, Chinese, etc.)")
    meal_type: str = Field(description="Meal type: breakfast, lunch, dinner, snack")
    description: Optional[str] = Field(default=None, description="Brief description of the dish")
    ingredients: List[IngredientSchema] = Field(description="List of ingredients with quantities")
    instructions: List[InstructionStepSchema] = Field(description="Step-by-step cooking instructions")
    prep_time_minutes: int = Field(description="Preparation time in minutes")
    cook_time_minutes: int = Field(description="Cooking time in minutes")
    servings: int = Field(default=2, description="Number of servings")
    nutrition: NutritionSchema = Field(description="Nutritional information per serving")
    diet_match_reasons: List[str] = Field(default_factory=list, description="Why this recipe matches the diet")
    warnings: List[str] = Field(default_factory=list, description="Any warnings or precautions")


class WeeklyScheduleDaySchema(BaseModel):
    breakfast: Optional[str] = Field(default=None, description="Recipe ID for breakfast")
    lunch: Optional[str] = Field(default=None, description="Recipe ID for lunch")
    dinner: Optional[str] = Field(default=None, description="Recipe ID for dinner")
    snack: Optional[str] = Field(default=None, description="Recipe ID for snack")


class DietChartExtractionSchema(BaseModel):
    medical_condition: Optional[str] = Field(default=None, description="Detected medical condition")
    avoid_foods: List[str] = Field(default_factory=list, description="Foods to completely avoid")
    limit_foods: List[str] = Field(default_factory=list, description="Foods to limit/restrict portions")
    allowed_foods: List[str] = Field(default_factory=list, description="Recommended/allowed foods")
    meal_frequency: Optional[int] = Field(default=3, description="Number of meals per day recommended")
    calorie_limit: Optional[int] = Field(default=None, description="Daily calorie limit if specified")
    salt_limit: Optional[str] = Field(default=None, description="Salt restriction level")
    doctor_notes: Optional[str] = Field(default=None, description="Additional notes from doctor/dietitian")
    extraction_confidence: str = Field(default="high", description="Confidence level: high/medium/low")
    unreadable_sections: List[str] = Field(default_factory=list, description="Parts that couldn't be clearly read")


class DietProfileCreateRequest(BaseModel):
    profile_name: Optional[str] = Field(default=None, description="Optional name for the diet profile")
    
    medical_condition: Optional[str] = Field(default=None)
    avoid_foods: List[str] = Field(default_factory=list)
    limit_foods: List[str] = Field(default_factory=list)
    allowed_foods: List[str] = Field(default_factory=list)
    meal_frequency: Optional[int] = Field(default=3)
    calorie_limit: Optional[int] = Field(default=None)
    salt_limit: Optional[str] = Field(default=None)
    doctor_notes: Optional[str] = Field(default=None)
    
    cuisine: List[str] = Field(default_factory=list)
    diet_type: Optional[str] = Field(default=None)
    allergies: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    cooking_time_pref: Optional[str] = Field(default=None)
    budget_level: Optional[str] = Field(default=None)


class DietProfileUpdateRequest(BaseModel):
    profile_name: Optional[str] = None
    
    medical_condition: Optional[str] = None
    avoid_foods: Optional[List[str]] = None
    limit_foods: Optional[List[str]] = None
    allowed_foods: Optional[List[str]] = None
    meal_frequency: Optional[int] = None
    calorie_limit: Optional[int] = None
    salt_limit: Optional[str] = None
    doctor_notes: Optional[str] = None
    extraction_status: Optional[str] = None
    
    cuisine: Optional[List[str]] = None
    diet_type: Optional[str] = None
    allergies: Optional[List[str]] = None
    disliked_ingredients: Optional[List[str]] = None
    cooking_time_pref: Optional[str] = None
    budget_level: Optional[str] = None


class NutritionTargetsResponse(BaseModel):
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    water_ml: Optional[int] = None


class MealPlanItemResponse(BaseModel):
    name: str
    quantity: Optional[str] = None
    notes: Optional[str] = None


class MealPlanTargetResponse(BaseModel):
    meal_type: str
    foods: List[MealPlanItemResponse] = []
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    timing: Optional[str] = None
    notes: Optional[str] = None


class DietProfileResponse(BaseModel):
    id: str
    user_id: str
    profile_name: Optional[str]
    source_file_url: Optional[str]
    
    medical_condition: Optional[str]
    avoid_foods: List[str]
    limit_foods: List[str]
    allowed_foods: List[str]
    meal_frequency: Optional[int]
    calorie_limit: Optional[int]
    salt_limit: Optional[str]
    doctor_notes: Optional[str]
    extraction_status: str
    extracted_raw_text: Optional[str]
    
    nutrition_targets: Dict[str, Any] = {}
    meal_plans: List[Dict[str, Any]] = []
    
    cuisine: List[str]
    diet_type: Optional[str]
    allergies: List[str]
    disliked_ingredients: List[str]
    cooking_time_pref: Optional[str]
    budget_level: Optional[str]
    
    is_active: bool
    created_at: str
    updated_at: str


class RecipeGenerateRequest(BaseModel):
    diet_profile_id: str = Field(description="ID of the diet profile to use")
    meal_type: Optional[str] = Field(default=None, description="Meal type for on-demand: breakfast, lunch, dinner, snack")
    cuisine_override: Optional[List[str]] = Field(default=None, description="Override cuisine preference for this request")
    

class WeeklyScheduleGenerateRequest(BaseModel):
    diet_profile_id: str = Field(description="ID of the diet profile to use")
    week_start_date: Optional[date] = Field(default=None, description="Start date for the week (defaults to next Monday)")
    cuisine_override: Optional[List[str]] = Field(default=None, description="Override cuisine preference for this request")


class RecipeResponse(BaseModel):
    id: str
    user_id: str
    diet_profile_id: Optional[str]
    
    recipe_name: str
    cuisine: Optional[str]
    meal_type: str
    description: Optional[str]
    
    ingredients: List[Dict[str, Any]]
    instructions: List[Dict[str, Any]]
    
    prep_time_minutes: Optional[int]
    cook_time_minutes: Optional[int]
    servings: int
    
    nutrition: Dict[str, Any]
    
    diet_match_reasons: List[str]
    warnings: List[str]
    
    is_favorite: bool
    source_type: str
    
    created_at: str


class WeeklyScheduleResponse(BaseModel):
    id: str
    user_id: str
    diet_profile_id: Optional[str]
    
    week_start_date: date
    
    monday: Dict[str, Any]
    tuesday: Dict[str, Any]
    wednesday: Dict[str, Any]
    thursday: Dict[str, Any]
    friday: Dict[str, Any]
    saturday: Dict[str, Any]
    sunday: Dict[str, Any]
    
    compliance_score: int
    is_active: bool
    created_at: str


class WeeklyScheduleWithRecipesResponse(BaseModel):
    id: str
    user_id: str
    diet_profile_id: Optional[str]
    week_start_date: date
    compliance_score: int
    is_active: bool
    created_at: str
    days: Dict[str, Dict[str, Any]] = Field(description="Map of day name to recipe details")


class RecipeTrackRequest(BaseModel):
    recipe_id: str = Field(description="ID of the recipe to track")
    scheduled_date: Optional[date] = Field(default=None, description="Date the meal was scheduled")
    status: str = Field(default="ate", description="Status: cooked, ate, skipped, replaced")


class RecipeTrackResponse(BaseModel):
    id: str
    user_id: str
    recipe_id: str
    meal_event_id: Optional[str]
    scheduled_date: Optional[date]
    status: str
    created_at: str
    recipe_name: Optional[str] = None
    nutrition_added: Optional[Dict[str, Any]] = None
