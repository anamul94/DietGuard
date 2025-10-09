import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse


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
            "openai.gpt-oss-20b-1:0",
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
            "- MUST extract and state exact nutrition values from the report\n"
            "- Include Calories, Protein, Carbs, Fat, Fiber, Sugar with exact numbers\n"
            "- Provide clinical assessment\n"
            "- Give specific recommendations\n"
            "- Suggest next meal options\n\n"
            "Requirements:\n"
            "- Professional medical tone\n"
            "- Direct, clear statements\n"
            "- Extract precise nutritional data from the report\n"
            "- No casual phrases or questions\n"
            "- No introductory or closing remarks\n"
            "- Suitable for speech synthesis\n\n"
            "Example:\n"
            "Calories: 450. Protein: 35 grams. Carbs: 35 grams. Fat: 20 grams. Fiber: 6 grams. Sugar: 8 grams.\n\n"
            "This meal provides balanced macronutrients with adequate protein for muscle maintenance and moderate carbohydrates for sustained energy.\n\n"
            "Safe foods include lean proteins, vegetables, and whole grains. Limit processed items and added sugars.\n\n"
            "For your next meal, consider grilled fish with quinoa and steamed vegetables."
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
        # run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message], config={"callbacks": [get_langfuse_handler()]})
        )

        # Flush events to Langfuse
        flush_langfuse()

        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        return f"Model invocation failed: {str(e)}"
