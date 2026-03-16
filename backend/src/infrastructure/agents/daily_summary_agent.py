import asyncio
import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from .agent_response import AgentResponse
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from ..utils.logger import logger


class DailySummaryResult(BaseModel):
    narrative: str = Field(description="2-3 sentences overview, 1 key insight, 1-2 actions for tomorrow")
    alerts: List[str] = Field(default_factory=list, description="Any critical alerts based on the data")

MAX_NARRATIVE_WORDS = 90


def _normalize_narrative(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value

    # Avoid third-person robotic phrasing.
    value = re.sub(r"(?i)\\bthe user\\b", "you", value)
    value = re.sub(r"(?i)\\byou are\\b", "you're", value)

    # Collapse excessive whitespace.
    value = re.sub(r"\\s+", " ", value).strip()

    # Hard cap words to avoid long, generic narratives.
    words = value.split()
    if len(words) > MAX_NARRATIVE_WORDS:
        value = " ".join(words[:MAX_NARRATIVE_WORDS]).rstrip(" .") + "."
    return value


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

    # Convert context dict into a prompt-friendly string (keep it compact).
    meals = context.get("meals", []) or []
    vitals = context.get("vitals", []) or []
    total_calories = 0
    for meal in meals:
        try:
            total_calories += int(meal.get("calories") or 0)
        except Exception:
            continue

    stats_text = (
        f"Date: {context.get('target_date')}\n"
        f"Adherence Score: {context.get('adherence_score', 0)}/100\n"
        f"Meals Logged: {len(meals)}\n"
        f"Total Calories: {total_calories}\n"
        f"Vitals Logged: {len(vitals)}\n"
        f"Conditions: {context.get('conditions_snapshot')}\n"
    )

    base_system_content = (
        "You are a warm, concise daily health coach. "
        "Your task is to summarize the user's day in a friendly, non-clinical way.\n\n"
        "RULES:\n"
        "1. Output exactly 3 short sentences total: (a) overview, (b) 1 insight, (c) 1 next step.\n"
        "2. Keep it under 90 words. No filler, no greetings, no disclaimers.\n"
        "3. Speak directly to the person using 'you' (never 'the user').\n"
        "4. If data is missing, acknowledge it briefly and suggest what to log next.\n"
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
        if isinstance(structured_data.get("narrative"), str):
            structured_data["narrative"] = _normalize_narrative(structured_data["narrative"])
        
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
