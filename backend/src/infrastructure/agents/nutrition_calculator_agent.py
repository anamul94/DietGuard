import asyncio
from pydantic import BaseModel, Field
from typing import Any, Dict, List
from ..utils.logger import logger
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from ..utils.nutrition_utils import extract_food_item_names, metric_value
from .agent_response import AgentResponse
from ...presentation.schemas.food_schemas import FoodNutritionBreakdownItem, NutritionInfo


def _aggregate_nutrition_from_items(items: List[Dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metric_units = {
        "calories": "kcal",
        "protein": "g",
        "carbohydrates": "g",
        "fat": "g",
        "fiber": "g",
        "sugar": "g",
    }
    totals: dict[str, dict[str, Any]] = {
        metric: {"value": 0.0, "unit": unit} for metric, unit in metric_units.items()
    }

    for item in items:
        if not isinstance(item, dict):
            continue
        nutrition = item.get("nutrition") or {}
        if not isinstance(nutrition, dict):
            continue
        for metric, unit in metric_units.items():
            metric_entry = nutrition.get(metric)
            if metric_entry is None:
                continue
            value = metric_value(metric_entry)
            if value is None:
                continue
            totals[metric]["value"] += value

    return totals


class NutritionCalculation(BaseModel):
    """Complete nutrition calculation for food items"""
    fooditem_details: List[FoodNutritionBreakdownItem] = Field(
        default_factory=list,
        description="Per-item nutrition breakdown for each food item"
    )
    nutrition: NutritionInfo | None = Field(
        default=None,
        description="Total nutritional information for all food items combined. Optional when agent does not provide totals."
    )



async def nutrition_calculator_agent(fooditems: List[str]):
    """
    Calculate clinically accurate nutrition values for given food items.

    Used for fresh nutrition calculation from confirmed food items (no reference data).
    For recalculation with reference to old AI extraction, use nutrition_recalculator_agent instead.

    Args:
        fooditems: List of food item descriptions with quantities
                  (e.g., ["1 grilled chicken with naan roti", "2 slices pizza with cheese and tomato"])

    Returns:
        AgentResponse with structured NutritionCalculation data
    """
    item_count = len(fooditems)
    logger.info("Nutrition calculator agent invoked", item_count=item_count)
    
    try:
        diagnostics = get_chat_model_diagnostics(agent_name="nutrition_calculator_agent")
        llm = create_chat_model(agent_name="nutrition_calculator_agent", temperature=0.1)
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(NutritionCalculation, include_raw=True)
    except Exception as e:
        logger.error(
            "Nutrition calculator agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            diagnostics=diagnostics if "diagnostics" in locals() else None,
        )
        return AgentResponse.error_response("Nutrition calculation service is temporarily unavailable. Please try again later.")

    base_system_content = (
        "You are Dr. Sarah Mitchell, a board-certified clinical nutritionist and registered dietitian with 15 years of experience. "
        "Your specialty is providing clinically accurate nutritional analysis based on USDA FoodData Central and international nutrition databases. "
        "\n\nYOUR TASK:"
        "\nCalculate precise, clinically accurate nutritional values for the provided food items."
        "\n\nIMPORTANT GUIDELINES:"
        "\n1. **Accuracy**: Base all calculations on established nutrition databases (USDA FoodData Central, NCCDB)"
        "\n2. **Quantities**: Parse quantities from descriptions (e.g., '1 grilled chicken' = ~150g, '2 slices pizza' = ~200g)"
        "\n3. **Standard Servings**: Use standard serving sizes when quantities are not specified"
        "\n4. **Ingredients**: Account for all visible ingredients and preparation methods"
        "\n5. **Per-item breakdown**: Return `fooditem_details` with one entry per food item and that item's nutrition"
        "\n6. **Aggregation**: Provide TOTAL nutrition for ALL items combined"
        "\n7. **Clinical Standards**: Ensure values are realistic and medically sound"
        "\n8. **Precision**: Round to whole numbers for calories, use grams (g) for macros"
        "\n9. **Output format**: Each nutrition field must be an object with `value` and `unit`."
        "\n   Example: calories={\"value\": 450, \"unit\": \"kcal\"}, protein={\"value\": 35, \"unit\": \"g\"}"
    )
    
    base_system_content += (
        "\n\nSTANDARD SERVING SIZES (when not specified):"
        "\n- Pizza slice: 100-120g"
        "\n- Grilled chicken breast: 150g"
        "\n- Naan/roti: 80-100g"
        "\n- Rice (cooked): 150g"
        "\n- Salad: 100g"
        "\n\n**OUTPUT JSON STRUCTURE (REQUIRED):**"
        "\nYou MUST output EXACTLY this JSON structure with all fields:"
        "\n{"
        "\n  \"fooditem_details\": ["
        "\n    {"
        "\n      \"name\": \"item name\","
        "\n      \"quantity\": \"quantity with unit\","
        "\n      \"preparation\": \"preparation method if mentioned\","
        "\n      \"nutrition\": {"
        "\n        \"calories\": {\"value\": number, \"unit\": \"kcal\"},"
        "\n        \"protein\": {\"value\": number, \"unit\": \"g\"},"
        "\n        \"carbohydrates\": {\"value\": number, \"unit\": \"g\"},"
        "\n        \"fat\": {\"value\": number, \"unit\": \"g\"},"
        "\n        \"fiber\": {\"value\": number, \"unit\": \"g\"},"
        "\n        \"sugar\": {\"value\": number, \"unit\": \"g\"}"
        "\n      }"
        "\n    }"
        "\n  ],"
        "\n  \"nutrition\": {"
        "\n    \"calories\": {\"value\": TOTAL_CALORIES, \"unit\": \"kcal\"},"
        "\n    \"protein\": {\"value\": TOTAL_PROTEIN, \"unit\": \"g\"},"
        "\n    \"carbohydrates\": {\"value\": TOTAL_CARBS, \"unit\": \"g\"},"
        "\n    \"fat\": {\"value\": TOTAL_FAT, \"unit\": \"g\"},"
        "\n    \"fiber\": {\"value\": TOTAL_FIBER, \"unit\": \"g\"},"
        "\n    \"sugar\": {\"value\": TOTAL_SUGAR, \"unit\": \"g\"}"
        "\n  }"
        "\n}"
        "\n\nIMPORTANT: Each item in 'fooditem_details' has its own 'nutrition' object."
        "\nThe top-level 'nutrition' field is the SUM of all fooditem_details.nutrition values."
        "\nBe precise, objective, and clinically accurate in all calculations."
    )
    
    system_message = {
        "role": "system",
        "content": base_system_content,
    }

    # Format food items for the prompt
    fooditems_text = "\n".join([f"- {item}" for item in fooditems])

    user_content = (
        f"Calculate the total nutritional values for these food items:\n\n{fooditems_text}\n\n"
        "Provide clinically accurate nutrition data based on standard serving sizes and the quantities mentioned.\n\n"
        "**REQUIRED OUTPUT:**\n"
        "1. `fooditem_details` array: One entry per food item with its individual nutrition\n"
        "2. `nutrition` object: The TOTAL/SUM of all individual nutrition values across all items\n\n"
        "CRITICAL: You MUST include BOTH fields in your response. The top-level `nutrition` field is mandatory "
        "and must be the sum of all items' nutrition values."
    )
    
    message = {
        "role": "user",
        "content": user_content,
    }

    try:
        # Invoke with structured output (returns dict with 'parsed' and 'raw')
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )

        parsed: NutritionCalculation | None = result.get("parsed")
        raw = result.get("raw")  # AIMessage with metadata
        parsing_error = result.get("parsing_error")

        # If LLM didn't include the top-level nutrition, calculate it from fooditem_details
        if parsed is None and parsing_error and "nutrition" in str(parsing_error).lower():
            logger.info("Attempting to calculate missing nutrition from fooditem_details")
            # Try to extract just the fooditem_details and calculate nutrition ourselves
            try:
                import json
                # Try to get the raw content - it might be in different formats
                if hasattr(raw, "content"):
                    raw_content = raw.content
                elif hasattr(raw, "additional_kwargs") and "tool_calls" in raw.additional_kwargs:
                    # Sometimes structured output is in tool_calls
                    raw_content = raw.additional_kwargs.get("tool_calls", [{}])[0].get("function", {}).get("arguments", "{}")
                else:
                    raw_content = str(raw)

                logger.info("Raw content type", content_type=type(raw_content).__name__)

                # Parse the content
                if isinstance(raw_content, str):
                    partial_data = json.loads(raw_content)
                elif isinstance(raw_content, dict):
                    partial_data = raw_content
                else:
                    logger.warning("Unexpected raw content type, cannot calculate nutrition")
                    partial_data = {}

                if "fooditem_details" in partial_data and partial_data["fooditem_details"]:
                    logger.info("Found fooditem_details, calculating totals", item_count=len(partial_data["fooditem_details"]))
                    # Calculate total nutrition from items
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

                    # Add the calculated nutrition and re-parse
                    partial_data["nutrition"] = totals
                    parsed = NutritionCalculation(**partial_data)
                    logger.info("Successfully calculated missing top-level nutrition", total_calories=totals["calories"]["value"])
                else:
                    logger.warning("No fooditem_details found in partial data")
            except Exception as calc_error:
                logger.error("Failed to calculate missing nutrition", error=str(calc_error), exception_type=type(calc_error).__name__)

        if parsed is None:
            error_payload = {
                "has_raw": raw is not None,
                "result_keys": list(result.keys()),
            }
            if parsing_error:
                error_payload["parsing_error"] = str(parsing_error)
            logger.error(
                "Nutrition calculator agent returned no structured output",
                item_count=item_count,
                llm_result_summary=error_payload,
            )
            return AgentResponse.error_response(
                "Nutrition calculation failed: LangChain could not parse the model output."
            )
        meta = raw.response_metadata if hasattr(raw, 'response_metadata') else {}
        usage = raw.usage_metadata if hasattr(raw, 'usage_metadata') else {}

        # Convert Pydantic model to dict for AgentResponse
        structured_data = parsed.model_dump()
        if structured_data.get("nutrition") is None:
            structured_data["nutrition"] = _aggregate_nutrition_from_items(
                structured_data.get("fooditem_details", [])
            )
        
        # Prepare metadata for token tracking
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }
        
        logger.info("Nutrition calculator agent completed successfully", 
                   item_count=item_count,
                   total_calories=metric_value(structured_data.get('nutrition', {}).get('calories')) or 0,
                   token_usage=usage)
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
            
    except Exception as e:
        logger.error("Nutrition calculator agent model invocation failed", 
                    error=str(e), 
                    exception_type=type(e).__name__, 
                    item_count=item_count)
        return AgentResponse.error_response("Unable to calculate nutrition values at this time. Please try again later.")
