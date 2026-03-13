import asyncio
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from ..utils.bedrock_utils import DEFAULT_BEDROCK_MODEL, create_bedrock_chat_model, get_bedrock_config


async def summary_agent(nutrition_report: str) -> str:
    """
    nutrition_report: Raw nutritional report text that needs a spoken-style summary
    """
    logger.info("Summary agent invoked")
    
    try:
        config = get_bedrock_config()
        llm = create_bedrock_chat_model()
    except Exception as e:
        logger.error(
            "Summary agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            has_region=bool(config.get("region_name")) if "config" in locals() else False,
            has_profile=bool(config.get("credentials_profile_name")) if "config" in locals() else False,
            has_session_token=bool(config.get("aws_session_token")) if "config" in locals() else False,
        )
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
        # run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message], config={"callbacks": [get_langfuse_handler()]})
        )

        # Flush events to Langfuse
        flush_langfuse()

        logger.info("Summary agent completed successfully")
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        logger.error("Summary agent model invocation failed", error=str(e), exception_type=type(e).__name__)
        return f"Model invocation failed: {str(e)}"
