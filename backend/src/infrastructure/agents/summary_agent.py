import asyncio
from ..utils.logger import logger
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics


async def summary_agent(nutrition_report: str) -> str:
    """
    nutrition_report: Raw nutritional report text that needs a spoken-style summary
    """
    logger.info("Summary agent invoked")
    
    try:
        diagnostics = get_chat_model_diagnostics(agent_name="summary_agent")
        llm = create_chat_model(agent_name="summary_agent")
    except Exception as e:
        logger.error(
            "Summary agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            diagnostics=diagnostics if "diagnostics" in locals() else None,
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
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message])
        )

        logger.info("Summary agent completed successfully")
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("Summary agent model invocation failed", error=str(e), exception_type=type(e).__name__)
        return f"Model invocation failed: {str(e)}"
