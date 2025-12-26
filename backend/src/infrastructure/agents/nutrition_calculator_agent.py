import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from .agent_response import AgentResponse


# Pydantic models for structured output
class NutritionInfo(BaseModel):
    """Nutritional information"""
    calories: int = Field(description="Total calories as integer", ge=0)
    protein: str = Field(description="Protein content with unit (e.g., '45g')")
    carbohydrates: str = Field(description="Carbohydrate content with unit (e.g., '12g')")
    fat: str = Field(description="Fat content with unit (e.g., '48g')")
    fiber: str = Field(description="Fiber content with unit (e.g., '1g')")
    sugar: str = Field(description="Sugar content with unit (e.g., '8g')")


class NutritionCalculation(BaseModel):
    """Complete nutrition calculation for food items"""
    fooditems: List[str] = Field(
        description="List of food items that were analyzed (echoed back from input)"
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
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Nutrition calculator agent configuration error - missing AWS credentials", 
                    has_key=bool(aws_key), has_secret=bool(aws_secret), has_region=bool(aws_region))
        return AgentResponse.error_response("Configuration error. Please try again later.")

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
            temperature=0.1,
        )
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(NutritionCalculation, include_raw=True)
    except Exception as e:
        logger.error("Nutrition calculator agent LLM initialization failed", error=str(e), exception_type=type(e).__name__)
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
        "\n5. **Aggregation**: Provide TOTAL nutrition for ALL items combined"
        "\n6. **Clinical Standards**: Ensure values are realistic and medically sound"
        "\n7. **Precision**: Round to whole numbers for calories, use grams (g) for macros"
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
        old_items = old_food_analysis.get("fooditems", [])
        old_nutrition = old_food_analysis.get("nutrition", {})
        
        reference_text = (
            "\n**REFERENCE - Previous Analysis:**\n"
            f"Previous food items: {', '.join(old_items)}\n"
            f"Previous nutrition values: {old_nutrition}\n\n"
            "Use this reference to maintain consistent calculation methodology. "
            "Recalculate ALL items in the new list above with the same standards.\n\n"
        )
        user_content += reference_text
    
    user_content += "Provide clinically accurate nutrition data based on standard serving sizes and the quantities mentioned."
    
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
        print(f"Response Metadata: {meta}")
        print(f"Usage Metadata: {usage}")
        print("=" * 50)
        
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
                   total_calories=structured_data.get('nutrition', {}).get('calories', 0),
                   token_usage=usage)
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
            
    except Exception as e:
        logger.error("Nutrition calculator agent model invocation failed", 
                    error=str(e), 
                    exception_type=type(e).__name__, 
                    item_count=item_count)
        return AgentResponse.error_response("Unable to calculate nutrition values at this time. Please try again later.")
