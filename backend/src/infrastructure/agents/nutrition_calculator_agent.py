import asyncio
from pydantic import BaseModel, Field
from typing import List
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from ..utils.bedrock_utils import DEFAULT_BEDROCK_MODEL, create_bedrock_chat_model, get_bedrock_config
from ..utils.nutrition_utils import extract_food_item_names, metric_value
from .agent_response import AgentResponse
from ...presentation.schemas.food_schemas import FoodNutritionBreakdownItem, NutritionInfo


class NutritionCalculation(BaseModel):
    """Complete nutrition calculation for food items"""
    fooditem_details: List[FoodNutritionBreakdownItem] = Field(
        default_factory=list,
        description="Per-item nutrition breakdown for each food item"
    )
    nutrition: NutritionInfo = Field(description="Total nutritional information for all food items combined")



async def nutrition_calculator_agent(fooditems: List[str], old_food_analysis: dict = None):
    """
    Calculate clinically accurate nutrition values for given food items.
    
    Args:
        fooditems: List of food item descriptions with quantities
                  (e.g., ["1 grilled chicken with naan roti", "2 slices pizza with cheese and tomato"])
        old_food_analysis: Optional previous food analysis with nutrition values for reference
                          to maintain calculation consistency (e.g., {"fooditems": [...], "nutrition": {...}})
        
    Returns:
        AgentResponse with structured NutritionCalculation data
    """
    item_count = len(fooditems)
    has_reference = old_food_analysis is not None
    logger.info("Nutrition calculator agent invoked", item_count=item_count, has_reference=has_reference)
    
    try:
        config = get_bedrock_config()
        llm = create_bedrock_chat_model(temperature=0.1)
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(NutritionCalculation, include_raw=True)
    except Exception as e:
        logger.error(
            "Nutrition calculator agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            has_region=bool(config.get("region_name")) if "config" in locals() else False,
            has_profile=bool(config.get("credentials_profile_name")) if "config" in locals() else False,
            has_session_token=bool(config.get("aws_session_token")) if "config" in locals() else False,
        )
        return AgentResponse.error_response("Nutrition calculation service is temporarily unavailable. Please try again later.")

    # Build system message with optional reference context
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
    
    # Add reference context if old food analysis is provided
    if old_food_analysis:
        reference_context = (
            "\n\n**REFERENCE DATA FOR CONSISTENCY:**"
            "\nYou have been provided with a previous food analysis as reference. Use this to:"
            "\n- Maintain consistent calculation methodology and standards"
            "\n- Apply the same serving size assumptions and quantity interpretations"
            "\n- Ensure consistency in how you calculate nutrition values"
            "\n- The reference is for maintaining calculation consistency only"
            "\n- You MUST recalculate ALL items in the new food list from scratch"
            "\n- Even if some items appear similar, calculate fresh values for the new list"
        )
        base_system_content += reference_context
    
    base_system_content += (
        "\n\nSTANDARD SERVING SIZES (when not specified):"
        "\n- Pizza slice: 100-120g"
        "\n- Grilled chicken breast: 150g"
        "\n- Naan/roti: 80-100g"
        "\n- Rice (cooked): 150g"
        "\n- Salad: 100g"
        "\n\nBe precise, objective, and clinically accurate in all calculations."
    )
    
    system_message = {
        "role": "system",
        "content": base_system_content,
    }

    # Format food items for the prompt
    fooditems_text = "\n".join([f"- {item}" for item in fooditems])
    
    # Build user message with optional reference data
    user_content = f"Calculate the total nutritional values for these food items:\n\n{fooditems_text}\n\n"
    
    if old_food_analysis:
        old_items = extract_food_item_names(old_food_analysis)
        old_nutrition = old_food_analysis.get("nutrition", {})
        
        reference_text = (
            "\n**REFERENCE - Previous Analysis:**\n"
            f"Previous food items: {', '.join(old_items)}\n"
            f"Previous nutrition values: {old_nutrition}\n\n"
            "Use this reference to maintain consistent calculation methodology. "
            "Recalculate ALL items in the new list above with the same standards.\n\n"
        )
        user_content += reference_text
    
    user_content += (
        "Provide clinically accurate nutrition data based on standard serving sizes and the quantities mentioned. "
        "Return both item-level nutrition in `fooditem_details` and total meal nutrition in `nutrition`."
    )
    
    message = {
        "role": "user",
        "content": user_content,
    }

    try:
        # Invoke with structured output (returns dict with 'parsed' and 'raw')
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke(
                [system_message, message],
                config={"callbacks": [get_langfuse_handler()]}
            )
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        # Extract parsed data and metadata
        parsed: NutritionCalculation = result["parsed"]
        raw = result["raw"]  # AIMessage with metadata
        meta = raw.response_metadata if hasattr(raw, 'response_metadata') else {}
        usage = raw.usage_metadata if hasattr(raw, 'usage_metadata') else {}
        
        # Print metadata for debugging
        print("=" * 50)
        print("NUTRITION CALCULATOR AGENT METADATA")
        print("=" * 50)
        # print(f"Response Metadata: {meta}")
        # print(f"Usage Metadata: {usage}")
        # print("=" * 50)
        
        # Convert Pydantic model to dict for AgentResponse
        structured_data = parsed.model_dump()
        
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
