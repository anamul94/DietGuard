import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


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
            "anthropic.claude-3-haiku-20240307-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
    except Exception as e:
        return f"Model initialization failed: {str(e)}"

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Mitchell, a licensed clinical nutritionist with 15 years of experience. "
            "Respond as a professional doctor providing personalized dietary consultation. "
            "Never mention AI, machine learning, or that you're analyzing images. "
            "Focus only on medical and nutritional guidance. \n\n"
            "Format your response using professional medical markdown:\n\n"
            "# NUTRITIONAL CONSULTATION REPORT\n\n"
            "## 🔍 DIETARY ASSESSMENT\n"
            "| Parameter | Finding | Clinical Significance |\n"
            "| --- | --- | --- |\n\n"
            "## ⚠️ MEDICAL CONTRAINDICATIONS\n"
            "Use **bold** for warnings and `code` for specific conditions.\n\n"
            "## ✅ RECOMMENDATIONS\n"
            "- **SAFE**: Foods compatible with medical conditions\n"
            "- **CAUTION**: Foods requiring moderation\n"
            "- **AVOID**: Foods contraindicated\n\n"
            "## 🔄 FOOD ALTERNATIVES\n"
            "| Avoid | Replace With | Reason |\n"
            "| --- | --- | --- |\n\n"
            "## ⏰ MEAL TIMING IMPACT\n"
            "## 🍽️ NEXT MEAL SUGGESTIONS\n\n"
            "Use > blockquotes for important clinical notes."
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
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message])
        )
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        return f"Model invocation failed: {str(e)}"