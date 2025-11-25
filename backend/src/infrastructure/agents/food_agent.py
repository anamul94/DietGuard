import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from .agent_response import AgentResponse


async def food_agent(data, type: str, mime_type) -> AgentResponse:
    """
    data: base64-encoded string OR list of base64 strings for multiple images
    type: "image" OR list of "image" for multiple images
    mime_type: e.g. "image/jpeg" OR list of mime types for multiple images
    """
    image_count = len(data) if isinstance(data, list) else 1
    logger.info("Food agent invoked", image_count=image_count)
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Food agent configuration error - missing AWS credentials", 
                    has_key=bool(aws_key), has_secret=bool(aws_secret), has_region=bool(aws_region))
        return AgentResponse.error_response("Configuration error. Please try again later.")

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
            temperature=0.1,
        )
    except Exception as e:
        logger.error("Food agent LLM initialization failed", error=str(e), exception_type=type(e).__name__)
        return AgentResponse.error_response("Food analysis service is temporarily unavailable. Please try again later.")

    system_message = {
    "role": "system",
    "content": (
        "You are Dr. James Rodriguez, a certified nutritionist and food analyst. "
        "Your task is to professionally identify and analyze food items in images. "
        "Focus exclusively on food items — ignore people, utensils, backgrounds, or non-food elements. "
        "Your analysis must be precise, identifying each food item and estimating its quantity "
        "(e.g., '2 boiled eggs', '1 cup of rice', 'half an apple'). "
        "Be objective and concise — do not speculate or include unnecessary commentary. "
        "Do not mention images, detection, or AI-related processes.\n\n"
        "Format your response using **markdown tables** exactly as follows:\n\n"
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
        "Provide only the tables. Do not include summaries, recommendations, or extra commentary."
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
        
        logger.info("Food agent completed successfully", image_count=image_count)
        return AgentResponse.success_response(response.text() if hasattr(response, "text") else str(response))
    except Exception as e:
        logger.error("Food agent model invocation failed", error=str(e), exception_type=type(e).__name__, image_count=image_count)
        return AgentResponse.error_response("Unable to analyze food items at this time. Please try again later.") 
