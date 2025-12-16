import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from .agent_response import AgentResponse


async def nutritionist_agent(food_analysis: str, medical_report: str, meal_time: str, gender: str, age: int, weight: float, height: float) -> AgentResponse:
    """
    Generate personalized nutritionist recommendations based on food analysis and user profile.
    
    Args:
        food_analysis: Analysis from food agent
        medical_report: Medical report data
        meal_time: Time of meal (breakfast, lunch, dinner, snack)
        gender: User's gender
        age: User's age in years
        weight: User's weight in kg
        height: User's height in cm
        
    Returns:
        Nutritionist recommendations as string
    """
    logger.info("Nutritionist agent invoked", meal_time=meal_time, age=age, gender=gender)
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Nutritionist agent configuration error - missing AWS credentials")
        raise ValueError("Configuration error. Please try again later.")

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("Nutritionist agent LLM initialization failed", error=str(e))
        raise ValueError("Nutritionist service is temporarily unavailable. Please try again later.")

    # Calculate BMI
    height_m = height / 100  # Convert cm to meters
    bmi = weight / (height_m ** 2) if height_m > 0 else 0
    
    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Mitchell, a certified nutritionist and dietitian with 15 years of experience. "
            "Your role is to provide personalized, evidence-based nutritional advice tailored to the individual's profile. "
            "Analyze the food consumed and provide actionable recommendations considering their health status, "
            "body metrics, and dietary goals. Be professional, empathetic, and supportive in your guidance."
        ),
    }

    user_message = {
        "role": "user",
        "content": (
            f"**User Profile:**\n"
            f"- Age: {age} years\n"
            f"- Gender: {gender}\n"
            f"- Weight: {weight} kg\n"
            f"- Height: {height} cm\n"
            f"- BMI: {bmi:.1f}\n"
            f"- Meal Time: {meal_time}\n\n"
            f"**Food Analysis:**\n{food_analysis}\n\n"
            f"**Medical Report:**\n{medical_report}\n\n"
            "Based on this user's profile, the food they consumed, and their medical history, "
            "provide personalized nutritionist recommendations. Include:\n"
            "1. Overall assessment of this meal\n"
            "2. Nutritional strengths and concerns\n"
            "3. Specific recommendations for improvement\n"
            "4. Suggestions for complementary foods\n"
            "5. Any warnings or cautions based on their health profile\n\n"
            "Keep your response concise, actionable, and encouraging."
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
        
        # Print metadata for debugging
        print("=" * 50)
        print("NUTRITIONIST AGENT METADATA")
        print("=" * 50)
        print(f"Response Metadata: {meta}")
        print(f"Usage Metadata: {usage}")
        print("=" * 50)
        
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
                   meal_time=meal_time, 
                   age=age, 
                   gender=gender,
                   token_usage=usage)
        
        return AgentResponse.success_response(response_text, metadata=metadata)
    except Exception as e:
        logger.error("Nutritionist agent model invocation failed", error=str(e), exception_type=type(e).__name__, meal_time=meal_time)
        return AgentResponse.error_response(f"Unable to generate nutritionist recommendations at this time. Please try again later.")