import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_ollama import ChatOllama

from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse


async def nutritionist_agent(food_analysis: str, medical_report: str, meal_time: str) -> str:
    """
    food_analysis: Analysis from food agent
    medical_report: Medical report data from Redis
    meal_time: Time when food is consumed (breakfast, lunch, dinner, snack)
    """
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        return f"Environment variables not loaded. AWS_ACCESS_KEY_ID: {'✓' if aws_key else '✗'}, AWS_SECRET_ACCESS_KEY: {'✓' if aws_secret else '✗'}, AWS_REGION: {'✓' if aws_region else '✗'}"

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
        ollam_llm = init_chat_model(
            "glm-4.7-flash:latest",
            model_provider="ollama",
        )
            
    except Exception as e:
        return f"Model initialization failed: {str(e)}"

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Mitchell, a licensed clinical nutritionist. "
            "Provide concise dietary consultation. Never mention AI or image analysis. "
            "Keep responses brief and tabular.\n\n"
            "Format:\n\n"
            "# NUTRITIONAL CONSULTATION REPORT\n\n"
            "## 🥗 CONSUMED FOOD ITEMS\n"
            "List specific food items identified.\n\n"
            "## 🔍 DIETARY ASSESSMENT\n"
            "| Parameter | Finding | Significance |\n"
            "| --- | --- | --- |\n\n"
            "## ⚠️ MEDICAL CONTRAINDICATIONS\n"
            "List conditions briefly.\n\n"
            "## ✅ RECOMMENDATIONS\n"
            "- **SAFE**: Food names only\n"
            "- **CAUTION**: Food names only\n"
            "- **AVOID**: Food names only\n\n"
            "## 🔄 FOOD ALTERNATIVES\n"
            "| Avoid | Replace With |\n"
            "| --- | --- |\n\n"
            "## ⏰ MEAL TIMING IMPACT\n"
            "Brief impact statement.\n\n"
            "## 🍽️ NEXT MEAL SUGGESTIONS\n"
            "Food names only."
        )
    }

    message = {
        "role": "user",
        "content": [
            {
                "type": "text", 
                "text": f"""
                PATIENT MEDICAL REPORT:
                {medical_report}
                
                CURRENT FOOD ANALYSIS:
                {food_analysis}
                
                MEAL TIME: {meal_time}
                
                Please provide comprehensive nutritional guidance considering the patient's medical conditions, current food intake, and meal timing.
                """
            }
        ],
    }

    try:
        # run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: ollam_llm.invoke([system_message, message], config={"callbacks": [get_langfuse_handler()]})
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        return f"Model invocation failed: {str(e)}"