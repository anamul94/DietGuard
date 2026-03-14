import asyncio
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from ..utils.bedrock_utils import create_bedrock_chat_model, get_bedrock_config
from ..utils.nutrition_utils import format_metric
from .agent_response import AgentResponse


async def nutritionist_agent(
    food_analysis: str, 
    medical_report: str, 
    meal_type: str,
    meal_time: str,  # NEW: Time when meal was consumed (HH:MM)
    gender: str, 
    age: int, 
    weight: float, 
    height: float,
    nutrition_values: dict = None
) -> AgentResponse:
    """
    Generate personalized nutritionist recommendations based on food analysis and user profile.
    
    Args:
        food_analysis: Analysis from food agent (food items as string)
        medical_report: Medical report data
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
        meal_time: Time when meal was consumed (HH:MM format)
        gender: User's gender
        age: User's age in years
        weight: User's weight in kg
        height: User's height in cm
        nutrition_values: Optional dict with nutrition data (calories, protein, carbs, fat, fiber, sugar)
        
    Returns:
        Nutritionist recommendations as string
    """
    logger.info("Nutritionist agent invoked", meal_type=meal_type, meal_time=meal_time, age=age, gender=gender, has_nutrition=bool(nutrition_values))
    
    try:
        config = get_bedrock_config()
        llm = create_bedrock_chat_model(temperature=0.1)
    except Exception as e:
        logger.error(
            "Nutritionist agent LLM initialization failed",
            error=str(e),
            has_region=bool(config.get("region_name")) if "config" in locals() else False,
            has_profile=bool(config.get("credentials_profile_name")) if "config" in locals() else False,
            has_session_token=bool(config.get("aws_session_token")) if "config" in locals() else False,
        )
        raise ValueError("Nutritionist service is temporarily unavailable. Please try again later.")

    
    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Mitchell, a certified nutritionist and dietitian with 15 years of experience. "
            "Your role is to provide personalized, evidence-based nutritional advice focused on the food consumed. "
            "Analyze the meal and provide actionable recommendations. If user profile data (age, weight, height) "
            "appears incomplete or unusual, focus your analysis on the food itself and general healthy eating principles. "
            "Be professional, practical, and encouraging. Avoid dwelling on missing or unusual profile data."
        ),
    }

    # Build nutrition section if values are provided
    nutrition_section = ""
    if nutrition_values:
        nutrition_section = (
            f"**Nutritional Breakdown:**\n"
            f"- Calories: {format_metric(nutrition_values.get('calories'), 'kcal') if nutrition_values.get('calories') is not None else 'N/A'}\n"
            f"- Protein: {format_metric(nutrition_values.get('protein'), 'g') if nutrition_values.get('protein') is not None else 'N/A'}\n"
            f"- Carbohydrates: {format_metric(nutrition_values.get('carbohydrates'), 'g') if nutrition_values.get('carbohydrates') is not None else 'N/A'}\n"
            f"- Fat: {format_metric(nutrition_values.get('fat'), 'g') if nutrition_values.get('fat') is not None else 'N/A'}\n"
            f"- Fiber: {format_metric(nutrition_values.get('fiber'), 'g') if nutrition_values.get('fiber') is not None else 'N/A'}\n"
            f"- Sugar: {format_metric(nutrition_values.get('sugar'), 'g') if nutrition_values.get('sugar') is not None else 'N/A'}\n\n"
        )

    user_message = {
        "role": "user",
        "content": (
            f"**Meal Type:** {meal_type} (consumed at {meal_time})\n\n"
            f"**Food Consumed:**\n{food_analysis}\n\n"
            f"{nutrition_section}"
            f"**User Profile:**\n"
            f"- Age: {age} years\n"
            f"- Gender: {gender}\n"
            f"- Weight: {weight} kg\n"
            f"- Height: {height} cm\n\n"
            f"**Medical History:**\n{medical_report if medical_report else 'No medical history provided'}\n\n"
            "Provide a concise nutritional assessment of this meal. Include:\n"
            "1. **Meal Overview**: Brief assessment of the food choices\n"
            "2. **Nutritional Highlights**: What's good about this meal\n"
            "3. **Areas for Improvement**: Specific, actionable suggestions\n"
            "4. **Complementary Foods**: What to add or pair with this meal\n"
            "5. **Health Tips**: Any relevant advice based on the meal type and medical history\n\n"
            "Keep your response concise (max 200 words), practical, and encouraging. "
            "Focus on the food analysis rather than profile data concerns."
        ),
    }

    try:
        # run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, user_message], config={"callbacks": [get_langfuse_handler()]})
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        # Extract metadata
        meta = response.response_metadata if hasattr(response, 'response_metadata') else {}
        usage = response.usage_metadata if hasattr(response, 'usage_metadata') else {}

        # Prepare metadata for token tracking
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }
        
        # Get response text
        response_text = response.text() if hasattr(response, "text") else str(response)
        
        logger.info("Nutritionist agent completed successfully", 
                   meal_type=meal_type, 
                   age=age, 
                   gender=gender,
                   token_usage=usage)
        
        return AgentResponse.success_response(response_text, metadata=metadata)
    except Exception as e:
        logger.error("Nutritionist agent model invocation failed", error=str(e), exception_type=type(e).__name__, meal_type=meal_type)
        return AgentResponse.error_response(f"Unable to generate nutritionist recommendations at this time. Please try again later.")
