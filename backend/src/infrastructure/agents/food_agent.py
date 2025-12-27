import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from .agent_response import AgentResponse
from ...presentation.schemas.food_schemas import NutritionInfo, FoodAnalysis


async def food_agent(data, type, mime_type):
    """
    Analyze food images and return structured nutritional data.
    
    Args:
        data: base64-encoded string OR list of base64 strings for multiple images
        type: "image" OR list of "image" for multiple images
        mime_type: e.g. "image/jpeg" OR list of mime types for multiple images
        
    Returns:
        AgentResponse with structured FoodAnalysis data
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
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(FoodAnalysis, include_raw=True)
    except Exception as e:
        logger.error("Food agent LLM initialization failed", error=str(e), exception_type=type(e).__name__)
        return AgentResponse.error_response("Food analysis service is temporarily unavailable. Please try again later.")

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. James Rodriguez, a certified nutritionist and food analyst. "
            "Your task is to professionally identify and analyze ALL food items in images with detailed descriptions. "
            "\n\nIMPORTANT INSTRUCTIONS:"
            "\n1. Identify EVERY food item visible in the image(s)"
            "\n2. For each food item, provide a DETAILED description that includes:"
            "\n   - The main food item name"
            "\n   - Visible ingredients, toppings, or components"
            "\n   - Preparation method if identifiable (grilled, fried, boiled, baked, etc.)"
            "\n   - Examples: 'pizza with cheese and tomato', 'grilled chicken with naan roti', "
            "'caesar salad with croutons and parmesan cheese', 'fried rice with vegetables and egg'"
            "\n3. Focus exclusively on food items — ignore people, utensils, backgrounds, or non-food elements"
            "\n4. Provide accurate nutritional estimates for the TOTAL meal (sum of all items)"
            "\n5. Be objective and precise — do not speculate or include unnecessary commentary"
        ),
    }

    # Handle multiple images
    if isinstance(data, list):
        content = [{
            "type": "text", 
            "text": "Identify and analyze all food items in these images. Provide a combined analysis with total nutritional values for all items."
        }]
        for i, (img_data, img_type, img_mime) in enumerate(zip(data, type, mime_type)):
            content.append({
                "type": img_type,
                "source_type": "base64",
                "mime_type": img_mime,
                "data": img_data,
            })
    else:
        content = [
            {"type": "text", "text": "Identify and analyze all food items in this image. Provide total nutritional values."},
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
        parsed: FoodAnalysis = result["parsed"]
        raw = result["raw"]  # AIMessage with metadata
        meta = raw.response_metadata if hasattr(raw, 'response_metadata') else {}
        usage = raw.usage_metadata if hasattr(raw, 'usage_metadata') else {}
        
        # Print metadata for debugging
        print("=" * 50)
        print("FOOD AGENT METADATA")
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
        
        logger.info("Food agent completed successfully", 
                   image_count=image_count,
                   food_items_count=len(structured_data.get('fooditems', [])),
                   total_calories=structured_data.get('nutrition', {}).get('calories', 0),
                   token_usage=usage)
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
            
    except Exception as e:
        logger.error("Food agent model invocation failed", 
                    error=str(e), 
                    exception_type=type(e).__name__, 
                    image_count=image_count)
        return AgentResponse.error_response("Unable to analyze food items at this time. Please try again later.")
