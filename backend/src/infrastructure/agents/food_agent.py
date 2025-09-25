import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse


async def food_agent(data, type: str, mime_type) -> str:
    """
    data: base64-encoded string OR list of base64 strings for multiple images
    type: "image" OR list of "image" for multiple images
    mime_type: e.g. "image/jpeg" OR list of mime types for multiple images
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
            "You are Dr. James Rodriguez, a certified nutritionist and food analyst. "
            "Analyze food items professionally and provide detailed nutritional assessment. "
            "IMPORTANT: Focus ONLY on food items. Ignore any people, faces, or non-food elements in images. "
            "Never mention that you're analyzing images or using AI technology. "
            "Respond as if conducting a professional food consultation. \n\n"
            "Format your response using markdown with tables:\n\n"
            "## FOOD IDENTIFICATION\n"
            "| Food Item | Quantity | Preparation Method |\n"
            "| --- | --- | --- |\n\n"
            "## NUTRITIONAL BREAKDOWN\n"
            "| Nutrient | Amount | % Daily Value |\n"
            "| --- | --- | --- |\n"
            "| Calories | | |\n"
            "| Protein | | |\n"
            "| Carbohydrates | | |\n"
            "| Fat | | |\n"
            "| Fiber | | |\n"
            "| Sugar | | |\n\n"
            "## SUMMARY\n"
            "Provide professional assessment and recommendations."
        ),
    }

    # Handle multiple images
    if isinstance(data, list):
        content = [{"type": "text", "text": "Identify and analyze all food items in these images. Provide analysis for each image and a combined nutritional summary."}]
        for i, (img_data, img_type, img_mime) in enumerate(zip(data, type, mime_type)):
            content.append({
                "type": img_type,
                "source_type": "base64",
                "mime_type": img_mime,
                "data": img_data,
            })
    else:
        content = [
            {"type": "text", "text": "Identify and analyze all food items in this image."},
            {
                "type": type,
                "source_type": "base64",
                "mime_type": mime_type,
                "data": data,
            },
        ]

    message = {
        "role": "user",
        "content": content,
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
