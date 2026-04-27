import asyncio
import time
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .agent_response import AgentResponse
from ..utils.bedrock_utils import (
    build_llm_debug_payload,
    create_llm,
    get_agent_llm_config,
    get_chat_model_diagnostics,
    is_llm_debug_enabled,
)
from ..utils.logger import logger
from ...presentation.schemas.recipe_schemas import (
    IngredientSchema,
    InstructionStepSchema,
    NutritionSchema,
    RecipeSchema,
)


class IngredientOutput(BaseModel):
    name: str = Field(description="Ingredient name")
    quantity: str = Field(description="Quantity with unit (e.g., '2 cups', '500g')")
    notes: str | None = Field(default=None, description="Optional notes about the ingredient")


class InstructionOutput(BaseModel):
    step_number: int = Field(description="Step number in the cooking process")
    instruction: str = Field(description="Detailed instruction for this step")


class NutritionOutput(BaseModel):
    calories: int = Field(description="Calories per serving")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Carbohydrates in grams")
    fat_g: float = Field(description="Fat in grams")
    fiber_g: float | None = Field(default=None, description="Fiber in grams")
    sodium_mg: float | None = Field(default=None, description="Sodium in milligrams")
    sugar_g: float | None = Field(default=None, description="Sugar in grams")


class RecipeOutput(BaseModel):
    recipe_name: str = Field(description="Name of the recipe")
    cuisine: str = Field(description="Cuisine type (Indian, Italian, Chinese, etc.)")
    meal_type: str = Field(description="Meal type: breakfast, lunch, dinner, snack")
    description: str | None = Field(default=None, description="Brief description of the dish")
    ingredients: List[IngredientOutput] = Field(description="List of ingredients with quantities")
    instructions: List[InstructionOutput] = Field(description="Step-by-step cooking instructions")
    prep_time_minutes: int = Field(description="Preparation time in minutes")
    cook_time_minutes: int = Field(description="Cooking time in minutes")
    servings: int = Field(default=2, description="Number of servings")
    nutrition: NutritionOutput = Field(description="Nutritional information per serving")
    diet_match_reasons: List[str] = Field(default_factory=list, description="Why this recipe matches the diet")
    warnings: List[str] = Field(default_factory=list, description="Any warnings or precautions")


class WeeklyScheduleOutput(BaseModel):
    notes: str = Field(description="General advice for the weekly schedule")
    recipes: List[RecipeOutput] = Field(
        default_factory=list,
        description="List of recipes for the week (7 days x meals per day)"
    )


async def recipe_suggestion_agent(
    context: Dict[str, Any],
    request_mode: str = "on_demand"
) -> AgentResponse:
    """
    Generate recipes based on diet restrictions and user preferences.
    
    Args:
        context: Dict containing:
            - medical_condition: Optional medical condition
            - avoid_foods: List of foods to avoid
            - limit_foods: List of foods to limit
            - allowed_foods: List of allowed foods
            - meal_frequency: Number of meals per day
            - doctor_notes: Additional doctor notes
            - cuisine: List of preferred cuisines
            - diet_type: vegetarian/non_vegetarian/vegan
            - allergies: List of allergies
            - disliked_ingredients: List of disliked ingredients
            - cooking_time_pref: Preferred cooking time
            - calorie_target: Optional daily calorie target
            - meal_type: For on_demand mode
            - day_of_week: For schedule mode (0-6)
        request_mode: "on_demand" for single recipe, "weekly_schedule" for full week
    
    Returns:
        AgentResponse with RecipeOutput or WeeklyScheduleOutput
    """
    started_at = time.perf_counter()
    agent_name = "recipe_suggestion_agent"
    logger.info("Recipe suggestion agent invoked", request_mode=request_mode, context_keys=list(context.keys()))
    
    try:
        llm_settings = get_agent_llm_config(agent_name)
        diagnostics = get_chat_model_diagnostics(agent_name=agent_name, **llm_settings)
        logger.info("Recipe suggestion agent model config", **diagnostics)
        llm = create_llm(agent_name=agent_name, temperature=0.7, **llm_settings)
    except Exception as e:
        logger.error(
            "Recipe suggestion agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
        )
        return AgentResponse.error_response("Recipe suggestion service is temporarily unavailable.")
    
    avoid_foods = context.get("avoid_foods", [])
    limit_foods = context.get("limit_foods", [])
    allowed_foods = context.get("allowed_foods", [])
    allergies = context.get("allergies", [])
    medical_condition = context.get("medical_condition")
    cuisine = context.get("cuisine", ["Indian"])
    diet_type = context.get("diet_type", "non_vegetarian")
    cooking_time_pref = context.get("cooking_time_pref", "30_min")
    calorie_target = context.get("calorie_target")
    meal_frequency = context.get("meal_frequency", 3)
    doctor_notes = context.get("doctor_notes", "")
    disliked_ingredients = context.get("disliked_ingredients", [])
    
    safety_guards = f"""
SAFETY REQUIREMENTS (MUST FOLLOW RIGIDLY):
1. NEVER include ingredients from avoid_foods list: {avoid_foods}
2. LIMIT portions of: {limit_foods}
3. RESPECT all allergies: {allergies}
4. DO NOT make medical claims or diagnose conditions
5. DO NOT suggest stopping or changing medications
6. If medical condition ({medical_condition}) is present, be extra cautious with ingredient choices
7. Include clear warnings if any ingredient might conflict with restrictions

DO NOT include these foods under any circumstances: {avoid_foods}
AVOID these due to allergies: {allergies}
"""
    
    if medical_condition:
        condition_guidelines = {
            "diabetes": "Use low glycemic index ingredients. Avoid sugar, refined carbs. Focus on fiber-rich foods.",
            "hypertension": "Use low sodium. Avoid processed foods, pickles, salty snacks. Emphasize potassium-rich foods.",
            "kidney_disease": "Limit protein, potassium, and phosphorus. Avoid high-sodium foods.",
            "heart_disease": "Use heart-healthy fats. Limit saturated fats and sodium.",
            "pregnancy": "Avoid raw fish, unpasteurized dairy, high-mercury fish. Ensure adequate iron and folate.",
        }
        guideline = condition_guidelines.get(medical_condition.lower(), "Follow general healthy eating guidelines.")
        safety_guards += f"\nCONDITION-SPECIFIC GUIDELINE ({medical_condition}): {guideline}"
    
    cooking_time_map = {
        "15_min": "under 15 minutes - quick and simple recipes only",
        "30_min": "under 30 minutes - moderately quick recipes",
        "60_min": "under 1 hour - more elaborate recipes allowed",
    }
    cooking_time_desc = cooking_time_map.get(cooking_time_pref, "under 30 minutes")
    
    if request_mode == "weekly_schedule":
        output_schema = WeeklyScheduleOutput
        structured_llm = llm.with_structured_output(output_schema, include_raw=True)
        
        system_content = f"""
CRITICAL: All your responses must be in English only. No other language is permitted.

You are Chef Maria, a professional culinary expert specializing in therapeutic and medical nutrition.
Your task is to generate a personalized weekly meal schedule based on the user's diet restrictions.

{safety_guards}

CUISINE & CULTURAL CONSIDERATIONS:
- Preferred cuisines: {cuisine}
- Diet type: {diet_type}
- Cooking time preference: {cooking_time_desc}
- Disliked ingredients to avoid: {disliked_ingredients}

MEAL STRUCTURE:
- Generate {meal_frequency} meals per day for all 7 days (Monday=0 to Sunday=6)
- Meal types: breakfast, lunch, dinner, {"snack" if meal_frequency >= 4 else ""}
- Total meals: {7 * meal_frequency} recipes
- Distribute calories appropriately across meals to meet daily target of {calorie_target or 2000} kcal

RECIPE REQUIREMENTS:
- Each recipe must have clear ingredient list with quantities
- Step-by-step cooking instructions
- Estimated nutrition per serving (calories, protein, carbs, fat)
- Explain why it matches the user's diet restrictions
- Include prep time and cook time
- Suggest realistic serving sizes

DOCTOR'S NOTES TO CONSIDER:
{doctor_notes if doctor_notes else "No additional notes."}

OUTPUT: Generate a WeeklyScheduleOutput with notes and a list of {7 * meal_frequency} recipes.
Each recipe should include day_of_week and meal_type implicitly through the order in the list.
"""
        
        user_content = f"""Generate a complete 7-day meal schedule with {meal_frequency} meals per day.

User context:
{context}

Return structured recipes for all 7 days."""
    
    else:
        output_schema = RecipeOutput
        structured_llm = llm.with_structured_output(output_schema, include_raw=True)
        meal_type = context.get("meal_type", "lunch")
        
        system_content = f"""
CRITICAL: All your responses must be in English only. No other language is permitted.

You are Chef Maria, a professional culinary expert specializing in therapeutic and medical nutrition.
Your task is to generate a single personalized recipe based on the user's diet restrictions.

{safety_guards}

CUISINE & CULTURAL CONSIDERATIONS:
- Preferred cuisines: {cuisine}
- Diet type: {diet_type}
- Cooking time preference: {cooking_time_desc}
- Disliked ingredients to avoid: {disliked_ingredients}

MEAL TYPE: {meal_type}

RECIPE REQUIREMENTS:
- Clear ingredient list with quantities
- Step-by-step cooking instructions
- Estimated nutrition per serving (calories, protein, carbs, fat)
- Explain why it matches the user's diet restrictions
- Include prep time and cook time
- Suggest realistic serving sizes

TARGET CALORIES for this meal: Approximately {context.get('meal_calorie_target', 500)} kcal

DOCTOR'S NOTES TO CONSIDER:
{doctor_notes if doctor_notes else "No additional notes."}

OUTPUT: Generate a RecipeOutput for a {meal_type} that strictly follows all safety requirements.
"""
        
        user_content = f"""Generate a {meal_type} recipe that matches the user's diet restrictions.

User context:
{context}

Return a structured recipe with ingredients, instructions, and nutrition."""
    
    system_message = {
        "role": "system",
        "content": system_content,
    }
    
    message = {
        "role": "user",
        "content": user_content,
    }
    
    try:
        if is_llm_debug_enabled(agent_name):
            logger.debug(
                "Recipe suggestion agent LLM request payload",
                agent_name=agent_name,
                llm_messages=build_llm_debug_payload([system_message, message], agent_name=agent_name),
            )
        
        invoke_started_at = time.perf_counter()
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )
        invoke_duration_ms = round((time.perf_counter() - invoke_started_at) * 1000, 2)
        
        parsed = result["parsed"]
        structured_data = parsed.model_dump()
        
        raw = result["raw"]
        meta = getattr(raw, 'response_metadata', {})
        usage = getattr(raw, 'usage_metadata', {})
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        
        recipe_count = len(structured_data.get("recipes", [])) if request_mode == "weekly_schedule" else 1
        logger.info(
            "Recipe suggestion agent completed successfully",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            invoke_duration_ms=invoke_duration_ms,
            request_mode=request_mode,
            recipe_count=recipe_count,
            token_usage=usage,
        )
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
    
    except Exception as e:
        logger.error(
            "Recipe suggestion agent invocation failed",
            error=str(e),
            exception_type=type(e).__name__,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return AgentResponse.error_response("Unable to generate recipes at this time.")
