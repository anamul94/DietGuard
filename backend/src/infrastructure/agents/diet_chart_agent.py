import asyncio
import time
from typing import Dict, Any, List, Optional

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


class MealPlanItem(BaseModel):
    """A single food item within a meal."""
    name: str = Field(description="Food item name")
    quantity: str | None = Field(default=None, description="Quantity or portion size")
    notes: str | None = Field(default=None, description="Preparation notes or alternatives")


class MealPlanTarget(BaseModel):
    """Target/suggested meal plan for a specific meal type."""
    meal_type: str = Field(description="Meal type: breakfast, lunch, dinner, snack, etc.")
    foods: List[MealPlanItem] = Field(default_factory=list, description="List of food items for this meal")
    calories: int | None = Field(default=None, description="Target calories for this meal")
    protein_g: float | None = Field(default=None, description="Target protein in grams")
    carbs_g: float | None = Field(default=None, description="Target carbohydrates in grams")
    fat_g: float | None = Field(default=None, description="Target fat in grams")
    timing: str | None = Field(default=None, description="Suggested timing (e.g., '8:00 AM', 'afternoon')")
    notes: str | None = Field(default=None, description="Special instructions for this meal")


class NutritionTargets(BaseModel):
    """Daily nutrition targets from the diet plan."""
    calories: int | None = Field(default=None, description="Daily calorie target")
    protein_g: float | None = Field(default=None, description="Daily protein target in grams")
    carbs_g: float | None = Field(default=None, description="Daily carbohydrate target in grams")
    fat_g: float | None = Field(default=None, description="Daily fat target in grams")
    fiber_g: float | None = Field(default=None, description="Daily fiber target in grams")
    sodium_mg: float | None = Field(default=None, description="Daily sodium limit in mg")
    water_ml: int | None = Field(default=None, description="Daily water intake target in ml")


class DietChartExtraction(BaseModel):
    medical_condition: str | None = Field(
        default=None,
        description="Detected medical condition (diabetes, hypertension, kidney disease, etc.)"
    )
    avoid_foods: list[str] = Field(
        default_factory=list,
        description="Foods to completely avoid (sugar, fried food, red meat)"
    )
    limit_foods: list[str] = Field(
        default_factory=list,
        description="Foods to limit/restrict portions (rice, salt, carbs)"
    )
    allowed_foods: list[str] = Field(
        default_factory=list,
        description="Recommended/allowed foods (vegetables, lean protein)"
    )
    meal_frequency: int | None = Field(
        default=3,
        description="Number of meals per day recommended"
    )
    calorie_limit: int | None = Field(
        default=None,
        description="Daily calorie limit if specified"
    )
    salt_limit: str | None = Field(
        default=None,
        description="Salt restriction level (low sodium, no added salt)"
    )
    doctor_notes: str | None = Field(
        default=None,
        description="Additional notes from doctor/dietitian"
    )
    nutrition_targets: NutritionTargets | None = Field(
        default=None,
        description="Detailed daily nutrition targets if specified in the document"
    )
    meal_plans: List[MealPlanTarget] = Field(
        default_factory=list,
        description="Detailed meal-by-meal plan if specified in the document"
    )
    extraction_confidence: str = Field(
        default="high",
        description="Confidence level: high/medium/low"
    )
    unreadable_sections: list[str] = Field(
        default_factory=list,
        description="Parts that couldn't be clearly read"
    )


async def diet_chart_agent(
    data: str,
    file_type: str,
    mime_type: str,
    raw_text: str | None = None
) -> AgentResponse:
    """
    Parse doctor's diet charts, prescriptions, and nutritionist recommendations.
    
    Extracts structured diet restrictions from:
    - Diet charts from doctors/dietitians
    - Nutritionist meal plans
    - Medical prescriptions with dietary advice
    - Handwritten diet instructions
    
    Args:
        data: base64-encoded string of the file/image
        file_type: "image" | "file" | "text"
        mime_type: e.g. "image/jpeg" or "application/pdf"
        raw_text: Optional pre-extracted text (for manual entry)
    
    Returns:
        AgentResponse with DietChartExtraction JSON data
    """
    started_at = time.perf_counter()
    agent_name = "diet_chart_agent"
    logger.info("Diet chart agent invoked", file_type=file_type, mime_type=mime_type)
    
    if file_type not in ("image", "file", "text"):
        return AgentResponse.error_response(
            "This service only accepts image files, PDF documents, or text input. "
            "Please upload a diet chart or prescription."
        )
    
    allowed_mime_types = ("image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain")
    if file_type != "text" and mime_type not in allowed_mime_types:
        return AgentResponse.error_response(
            f"Unsupported file type: {mime_type}. "
            "Please upload a diet chart as JPEG, PNG, WebP, PDF, or enter text manually."
        )
    
    try:
        llm_settings = get_agent_llm_config(agent_name)
        diagnostics = get_chat_model_diagnostics(agent_name=agent_name, **llm_settings)
        logger.info("Diet chart agent model config", **diagnostics)
        llm = create_llm(agent_name=agent_name, temperature=0.0, **llm_settings)
        structured_llm = llm.with_structured_output(DietChartExtraction, include_raw=True)
    except Exception as e:
        logger.error(
            "Diet chart agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
        )
        return AgentResponse.error_response("Diet chart extraction service is temporarily unavailable.")
    
    system_content = (
        "CRITICAL: All your responses must be in English only. No other language is permitted.\n\n"
        "You are a clinical nutrition assistant that extracts diet restrictions from "
        "doctor's diet charts, prescriptions, and nutritionist recommendations.\n\n"
        "CRITICAL: You must output ONLY structured diet data, NOT medical advice.\n\n"
        "ACCEPTED DOCUMENT TYPES:\n"
        "- Diet charts from doctors or dietitians\n"
        "- Nutritionist meal plans and recommendations\n"
        "- Medical prescriptions with dietary advice\n"
        "- Handwritten diet instructions\n"
        "- Food restriction lists\n"
        "- Meal timing guidelines\n"
        "- Detailed meal-by-meal diet plans\n"
        "\n"
        "REJECTED CONTENT (return with extraction_confidence='none' and explain in doctor_notes):\n"
        "- General medical reports (lab results, X-rays) - these are handled by another system\n"
        "- Non-diet/non-food related documents\n"
        "- Random images not related to diet\n"
        "\n"
        "EXTRACTION RULES:\n"
        "1. Extract foods to AVOID completely (sugar, fried food, red meat, alcohol, etc.)\n"
        "2. Extract foods to LIMIT or restrict portions (rice, salt, carbohydrates, etc.)\n"
        "3. Extract foods that are ALLOWED or recommended (vegetables, lean protein, whole grains)\n"
        "4. Identify any medical condition mentioned (diabetes, hypertension, kidney disease, pregnancy, etc.)\n"
        "5. Note meal frequency recommendations (e.g., '5 small meals per day')\n"
        "6. Extract calorie limits if specified\n"
        "7. Note salt/sodium restrictions\n"
        "8. Capture any additional doctor notes\n"
        "\n"
        "DETAILED NUTRITION TARGETS:\n"
        "If the document specifies daily nutrition targets, extract them in nutrition_targets:\n"
        "- Daily calories, protein, carbs, fat, fiber targets\n"
        "- Sodium/salt limits in mg\n"
        "- Water intake recommendations\n"
        "\n"
        "DETAILED MEAL PLANS:\n"
        "If the document contains a meal-by-meal plan, extract each meal in meal_plans:\n"
        "- meal_type: breakfast, mid_morning, lunch, snack, dinner, etc.\n"
        "- foods: list of specific food items with quantities\n"
        "- calories, protein_g, carbs_g, fat_g: per-meal targets if specified\n"
        "- timing: suggested time (e.g., '8:00 AM', 'between meals')\n"
        "- notes: special instructions (e.g., 'eat slowly', 'with water')\n"
        "\n"
        "Example meal plan extraction:\n"
        "Document shows:\n"
        "  Breakfast (8 AM): 2 slices whole wheat bread, 1 boiled egg, 1 cup milk (300 kcal)\n"
        "  Lunch (1 PM): 1 cup rice, 100g grilled chicken, 1 cup vegetables (500 kcal)\n"
        "\n"
        "Extract as:\n"
        "  meal_plans: [\n"
        "    {\n"
        "      meal_type: 'breakfast',\n"
        "      foods: [\n"
        "        {name: 'whole wheat bread', quantity: '2 slices'},\n"
        "        {name: 'boiled egg', quantity: '1'},\n"
        "        {name: 'milk', quantity: '1 cup'}\n"
        "      ],\n"
        "      calories: 300,\n"
        "      timing: '8:00 AM'\n"
        "    },\n"
        "    {\n"
        "      meal_type: 'lunch',\n"
        "      foods: [\n"
        "        {name: 'rice', quantity: '1 cup'},\n"
        "        {name: 'grilled chicken', quantity: '100g'},\n"
        "        {name: 'vegetables', quantity: '1 cup'}\n"
        "      ],\n"
        "      calories: 500,\n"
        "      timing: '1:00 PM'\n"
        "    }\n"
        "  ]\n"
        "\n"
        "CONFIDENCE LEVELS:\n"
        "- 'high': Document is clearly a diet chart with legible instructions\n"
        "- 'medium': Document appears to be diet-related but some parts are unclear\n"
        "- 'low': Document may be diet-related but extraction is uncertain\n"
        "- 'none': Document is not diet-related or completely illegible\n"
        "\n"
        "IMPORTANT:\n"
        "- Do NOT diagnose conditions - only extract what is explicitly written\n"
        "- Do NOT add medical advice beyond what's in the document\n"
        "- If the document mentions 'low sodium', 'no added salt', etc., include in salt_limit\n"
        "- Preserve exact food names and quantities as written\n"
        "- If meal frequency is not specified, leave as null\n"
        "- If no detailed meal plan is in the document, leave meal_plans as empty list\n"
    )
    
    system_message = {
        "role": "system",
        "content": system_content,
    }
    
    user_content = "Extract all diet restrictions and food guidelines from this document into the structured format."
    
    if file_type == "text" and raw_text:
        message = {
            "role": "user",
            "content": f"{user_content}\n\nDocument text:\n{raw_text}",
        }
    else:
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_content},
                {
                    "type": file_type,
                    "source_type": "base64",
                    "mime_type": mime_type,
                    "data": data,
                    "name": "diet_chart"
                },
            ],
        }
    
    try:
        if is_llm_debug_enabled(agent_name):
            logger.debug(
                "Diet chart agent LLM request payload",
                agent_name=agent_name,
                llm_messages=build_llm_debug_payload([system_message, message], agent_name=agent_name),
            )
        
        invoke_started_at = time.perf_counter()
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )
        invoke_duration_ms = round((time.perf_counter() - invoke_started_at) * 1000, 2)
        
        parsed: DietChartExtraction = result["parsed"]
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
        
        logger.info(
            "Diet chart agent completed successfully",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            invoke_duration_ms=invoke_duration_ms,
            extraction_confidence=structured_data.get("extraction_confidence"),
            avoid_count=len(structured_data.get("avoid_foods", [])),
            limit_count=len(structured_data.get("limit_foods", [])),
            token_usage=usage,
        )
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
    
    except Exception as e:
        logger.error(
            "Diet chart agent invocation failed",
            error=str(e),
            exception_type=type(e).__name__,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return AgentResponse.error_response("Unable to extract diet restrictions at this time.")
