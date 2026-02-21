import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model



async def summary_agent(nutrition_report: str) -> str:
    """
    nutrition_report: Raw nutritional report text that needs a spoken-style summary
    """
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        return (
            "Environment variables not loaded. "
            f"AWS_ACCESS_KEY_ID: {'✓' if aws_key else '✗'}, "
            f"AWS_SECRET_ACCESS_KEY: {'✓' if aws_secret else '✗'}, "
            f"AWS_REGION: {'✓' if aws_region else '✗'}"
        )

    try:
        llm = init_chat_model(
            # "anthropic.claude-3-haiku-20240307-v1:0",
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
    except Exception as e:
        return f"Model initialization failed: {str(e)}"

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Mitchell providing a professional nutritional summary for text-to-speech. "
            "Speak directly as a doctor would to a patient.\n\n"
            "Format:\n"
            "- Start with: 'You have consumed [food items] for [meal time]'\n"
            "- State exact nutrition values with numbers\n"
            "- Brief clinical assessment\n"
            "- Medical considerations if applicable\n"
            "- Alternative suggestions\n\n"
            "Requirements:\n"
            "- Professional yet conversational tone\n"
            "- Keep it concise and interactive\n"
            "- Extract precise nutritional data\n"
            "- No lengthy explanations\n"
            "- Suitable for speech synthesis\n\n"
            "Example:\n"
            "You have consumed fried eggs with toast for breakfast. Calories: 170. Protein: 12 grams. Carbs: 24 grams. Fat: 11 grams. Fiber: 2 grams.\n\n"
            "This provides adequate protein but low fiber content. The frying method adds unnecessary saturated fat.\n\n"
            "Consider boiled eggs with whole grain toast instead. For your next meal, try oatmeal with Greek yogurt."
        ),
    }

    message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "Format the nutritional report below into the requested spoken summary. "
                    "Make sure the flow lines up with the system instructions.\n\n"
                    
                    f"{nutrition_report}"
                ),
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
