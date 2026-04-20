import asyncio
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from ..utils.logger import logger
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from ..utils.nutrition_utils import extract_food_item_names, metric_value
from .agent_response import AgentResponse
from ...presentation.schemas.food_schemas import FoodNutritionBreakdownItem, NutritionInfo


class NutritionRecalculation(BaseModel):
    """Recalculated nutrition for corrected food items"""
    fooditem_details: List[FoodNutritionBreakdownItem] = Field(
        default_factory=list,
        description="Per-item nutrition breakdown for each food item"
    )
    nutrition: NutritionInfo = Field(..., description="Total nutritional information for all food items combined")


async def nutrition_recalculator_agent(
    corrected_fooditems: List[str],
    old_food_analysis: Dict[str, Any]
) -> AgentResponse:
    """
    Recalculate nutrition when user corrects AI-identified food items.

    This agent is specifically designed for the correction flow where:
    1. food_agent initially extracts items from images (may be inaccurate)
    2. User corrects the food names/quantities
    3. This agent recalculates nutrition for the corrected list
    4. Old analysis is used as reference to maintain consistency for unchanged items

    Args:
        corrected_fooditems: List of corrected food item descriptions with quantities
                            (e.g., ["1 paratha", "2 fried eggs", "1 slice pizza"])
        old_food_analysis: Original food_agent output with fooditem_details and nutrition
                          Used as reference to maintain calculation consistency

    Returns:
        AgentResponse with structured NutritionRecalculation data
    """
    item_count = len(corrected_fooditems)
    logger.info("Nutrition recalculator agent invoked", item_count=item_count)

    try:
        diagnostics = get_chat_model_diagnostics(agent_name="nutrition_recalculator_agent")
        llm = create_chat_model(agent_name="nutrition_recalculator_agent", temperature=0.1)
        structured_llm = llm.with_structured_output(NutritionRecalculation, include_raw=True)
    except Exception as e:
        logger.error(
            "Nutrition recalculator agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            diagnostics=diagnostics if "diagnostics" in locals() else None,
        )
        return AgentResponse.error_response("Nutrition recalculation service is temporarily unavailable.")

    # Extract reference data from old analysis
    old_items = extract_food_item_names(old_food_analysis)
    old_nutrition = old_food_analysis.get("nutrition", {})
    old_details = old_food_analysis.get("fooditem_details", [])

    system_message = {
        "role": "system",
        "content": (
            "CRITICAL: All your responses must be in English only. No other language is permitted.\n\n"
            "You are Dr. Sarah Mitchell, a board-certified clinical nutritionist. "
            "Your task is to recalculate nutrition values when users correct AI-identified food items.\n\n"
            "**CONTEXT:**\n"
            "An AI previously analyzed a meal photo and extracted food items with nutrition values. "
            "The user has now corrected some food names/quantities. Your job is to recalculate nutrition "
            "for the corrected list.\n\n"
            "**IMPORTANT RULES:**\n"
            "1. Use the old analysis as reference for calculation methodology and serving sizes\n"
            "2. Recalculate ALL items in the corrected list from scratch\n"
            "3. Base calculations on USDA FoodData Central and international nutrition databases\n"
            "4. Parse quantities from descriptions (e.g., '1 paratha' = ~80g, '2 fried eggs' = ~100g)\n"
            "5. Use standard serving sizes when quantities are not specified\n\n"
            "**OUTPUT JSON STRUCTURE (REQUIRED):**\n"
            "{\n"
            "  \"fooditem_details\": [\n"
            "    {\n"
            "      \"name\": \"food item name\",\n"
            "      \"quantity\": \"quantity with unit\",\n"
            "      \"preparation\": \"preparation method if mentioned\",\n"
            "      \"nutrition\": {\n"
            "        \"calories\": {\"value\": number, \"unit\": \"kcal\"},\n"
            "        \"protein\": {\"value\": number, \"unit\": \"g\"},\n"
            "        \"carbohydrates\": {\"value\": number, \"unit\": \"g\"},\n"
            "        \"fat\": {\"value\": number, \"unit\": \"g\"},\n"
            "        \"fiber\": {\"value\": number, \"unit\": \"g\"},\n"
            "        \"sugar\": {\"value\": number, \"unit\": \"g\"}\n"
            "      }\n"
            "    }\n"
            "  ],\n"
            "  \"nutrition\": {\n"
            "    \"calories\": {\"value\": TOTAL_CALORIES, \"unit\": \"kcal\"},\n"
            "    \"protein\": {\"value\": TOTAL_PROTEIN, \"unit\": \"g\"},\n"
            "    \"carbohydrates\": {\"value\": TOTAL_CARBS, \"unit\": \"g\"},\n"
            "    \"fat\": {\"value\": TOTAL_FAT, \"unit\": \"g\"},\n"
            "    \"fiber\": {\"value\": TOTAL_FIBER, \"unit\": \"g\"},\n"
            "    \"sugar\": {\"value\": TOTAL_SUGAR, \"unit\": \"g\"}\n"
            "  }\n"
            "}\n\n"
            "CRITICAL: Each item in 'fooditem_details' has its own 'nutrition' object.\n"
            "The top-level 'nutrition' field is the SUM of all fooditem_details.nutrition values."
        ),
    }

    # Format corrected items for the prompt
    corrected_items_text = "\n".join([f"- {item}" for item in corrected_fooditems])

    # Format reference data
    old_items_text = "\n".join([f"- {item}" for item in old_items])

    user_content = (
        f"**CORRECTED FOOD ITEMS (User-edited):**\n{corrected_items_text}\n\n"
        f"**REFERENCE - Original AI Extraction:**\n"
        f"Original items: {old_items_text}\n"
        f"Original total nutrition: {old_nutrition}\n"
        f"Original item details: {old_details}\n\n"
        "**YOUR TASK:**\n"
        "Recalculate nutrition for the CORRECTED items above. Use the original analysis as reference "
        "for calculation methodology, but recalculate ALL values fresh for the corrected list.\n\n"
        "**REQUIRED OUTPUT:**\n"
        "1. `fooditem_details` array: One entry per corrected item with its nutrition\n"
        "2. `nutrition` object: The TOTAL/SUM of all individual nutrition values\n\n"
        "You MUST include BOTH fields. The top-level `nutrition` is mandatory."
    )

    message = {
        "role": "user",
        "content": user_content,
    }

    try:
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )

        parsed: NutritionRecalculation | None = result.get("parsed")
        raw = result.get("raw")
        parsing_error = result.get("parsing_error")

        # Fallback: calculate total nutrition if LLM didn't include it
        if parsed is None and parsing_error and "nutrition" in str(parsing_error).lower():
            try:
                import json
                raw_content = raw.content if hasattr(raw, "content") else str(raw)
                partial_data = json.loads(raw_content) if isinstance(raw_content, str) else raw_content

                if "fooditem_details" in partial_data and partial_data["fooditem_details"]:
                    totals = {
                        "calories": {"value": 0, "unit": "kcal"},
                        "protein": {"value": 0, "unit": "g"},
                        "carbohydrates": {"value": 0, "unit": "g"},
                        "fat": {"value": 0, "unit": "g"},
                        "fiber": {"value": 0, "unit": "g"},
                        "sugar": {"value": 0, "unit": "g"},
                    }
                    for item in partial_data["fooditem_details"]:
                        if "nutrition" in item:
                            for key in totals:
                                if key in item["nutrition"]:
                                    totals[key]["value"] += item["nutrition"][key].get("value", 0)

                    partial_data["nutrition"] = totals
                    parsed = NutritionRecalculation(**partial_data)
                    logger.info("Calculated missing top-level nutrition", item_count=item_count)
            except Exception as calc_error:
                logger.warning("Failed to calculate missing nutrition", error=str(calc_error))

        if parsed is None:
            error_payload = {
                "has_raw": raw is not None,
                "result_keys": list(result.keys()),
            }
            if parsing_error:
                error_payload["parsing_error"] = str(parsing_error)
            logger.error(
                "Nutrition recalculator agent returned no structured output",
                item_count=item_count,
                llm_result_summary=error_payload,
            )
            return AgentResponse.error_response(
                "Nutrition recalculation failed: Could not parse model output."
            )

        meta = raw.response_metadata if hasattr(raw, 'response_metadata') else {}
        usage = raw.usage_metadata if hasattr(raw, 'usage_metadata') else {}

        structured_data = parsed.model_dump()

        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }

        logger.info("Nutrition recalculator agent completed successfully",
                   item_count=item_count,
                   total_calories=metric_value(structured_data.get('nutrition', {}).get('calories')) or 0,
                   token_usage=usage)

        return AgentResponse.success_response(structured_data, metadata=metadata)

    except Exception as e:
        logger.error("Nutrition recalculator agent invocation failed",
                    error=str(e),
                    exception_type=type(e).__name__,
                    item_count=item_count)
        return AgentResponse.error_response("Unable to recalculate nutrition at this time.")
