import asyncio
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from .agent_response import AgentResponse
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from ..utils.logger import logger


class DailySummaryResult(BaseModel):
    narrative: str = Field(description="2-3 sentences overview, 1 key insight, 1-2 actions for tomorrow")
    alerts: List[str] = Field(default_factory=list, description="Any critical alerts based on the data")


async def daily_summary_agent(context: Dict[str, Any]) -> AgentResponse:
    """
    Generate an end-of-day health summary narrative based on the user's daily data.
    """
    logger.info("Daily summary agent invoked")
    
    try:
        diagnostics = get_chat_model_diagnostics(agent_name="daily_summary_agent")
        llm = create_chat_model(agent_name="daily_summary_agent", temperature=0.4)
        structured_llm = llm.with_structured_output(DailySummaryResult, include_raw=True)
    except Exception as e:
        logger.error(
            "Daily summary agent LLM initialization failed",
            error=str(e),
            diagnostics=diagnostics if "diagnostics" in locals() else None,
        )
        return AgentResponse.error_response("Daily summary generation service is unavailable.")

    # Convert context dict into a prompt-friendly string
    stats_text = (
        f"Date: {context.get('target_date')}\n"
        f"Adherence Score: {context.get('adherence_score', 0)}/100\n"
        f"Meals Logged: {len(context.get('meals', []))}\n"
        f"Vitals Logged: {len(context.get('vitals', []))}\n"
        f"Conditions: {context.get('conditions_snapshot')}\n"
    )

    base_system_content = (
        "You are Dr. Sarah Mitchell, acting as a warm, encouraging daily health coach. "
        "Your task is to review the user's daily health stats and generate a short, non-clinical narrative summary.\n\n"
        "RULES:\n"
        "1. Write a day overview (2-3 sentences), 1 key insight, and tomorrow's focus (1-2 actions).\n"
        "2. Keep the total length under 250 words.\n"
        "3. Tone should be warm, encouraging, but objective about the data.\n"
        "4. Output must match the JSON schema exactly."
    )
    
    system_message = {
        "role": "system",
        "content": base_system_content,
    }

    user_content = f"Generate a daily summary based on this data:\n{stats_text}\n\nReturn the structured narrative and alerts."
    
    message = {
        "role": "user",
        "content": user_content,
    }

    try:
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )
        
        parsed: DailySummaryResult = result["parsed"]
        structured_data = parsed.model_dump()
        
        raw = result["raw"]
        meta = getattr(raw, 'response_metadata', {})
        usage = getattr(raw, 'usage_metadata', {})
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        
        logger.info("Daily summary agent completed successfully")
        return AgentResponse.success_response(structured_data, metadata=metadata)
            
    except Exception as e:
        logger.error("Daily summary agent invocation failed", error=str(e))
        return AgentResponse.error_response("Unable to generate daily summary at this time.")
