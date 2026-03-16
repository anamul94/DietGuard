import asyncio
import re
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from .agent_response import AgentResponse
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from ..utils.logger import logger


class MoodCheckInAnalysisResult(BaseModel):
    primary_emotion: str = Field(description="Primary emotion as a single word.")
    secondary_emotions: List[str] = Field(default_factory=list, description="Secondary emotions (list).")
    stress_level: int = Field(description="Stress level 0-100.", ge=0, le=100)
    key_stress_indicators: List[str] = Field(default_factory=list, description="Key stress indicators found.")
    urgency_level: Literal["low", "medium", "high"] = Field(description="Urgency level.")
    summary: str = Field(description="One sentence summary.")

    @field_validator("primary_emotion")
    @classmethod
    def _primary_emotion_one_word(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("primary_emotion is required")
        # Enforce "one word" (no spaces/tabs/newlines).
        if any(ch.isspace() for ch in text):
            raise ValueError("primary_emotion must be a single word")
        return text.lower()

    @field_validator("summary")
    @classmethod
    def _summary_non_empty(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("summary is required")
        return text


def _normalize_user_friendly_summary(summary: str) -> str:
    # Make the summary feel like it's speaking to the person, not about them.
    text = (summary or "").strip()
    if not text:
        return text

    # Common robotic phrasing from models.
    text = re.sub(r"(?i)\\bthe user\\b", "you", text)
    text = re.sub(r"(?i)^user\\b", "You", text)
    text = re.sub(r"(?i)^you\\s+are\\b", "You're", text)

    # Capitalize first character.
    text = text[:1].upper() + text[1:]
    return text


async def mood_checkin_agent(transcribed_text: str) -> AgentResponse:
    logger.info("Mood check-in agent invoked")

    try:
        diagnostics = get_chat_model_diagnostics(agent_name="mood_checkin_agent")
        llm = create_chat_model(agent_name="mood_checkin_agent", temperature=0.2)
        structured_llm = llm.with_structured_output(MoodCheckInAnalysisResult, include_raw=True)
    except Exception as e:
        logger.error(
            "Mood check-in agent LLM initialization failed",
            error=str(e),
            diagnostics=diagnostics if "diagnostics" in locals() else None,
        )
        return AgentResponse.error_response("Mood analysis service is unavailable.")

    system_message = {
        "role": "system",
        "content": (
            "You analyze a user's journal-style text (transcribed from audio) and extract emotional state.\n"
            "Return JSON that matches the schema exactly.\n\n"
            "Rules:\n"
            "- primary_emotion must be exactly one lowercase word (e.g. 'anxious', 'sad', 'calm').\n"
            "- secondary_emotions is a short list of additional emotion words.\n"
            "- stress_level is an integer from 0 to 100.\n"
            "- key_stress_indicators is a list of short phrases quoted or inferred from the text.\n"
            "- urgency_level is low/medium/high based on how acute the situation sounds.\n"
            "- summary is one sentence addressed directly to the person (use 'you', not 'the user'), polite and empathetic, no medical claims.\n"
        ),
    }

    user_message = {
        "role": "user",
        "content": f'Transcribed text:\n"""\n{transcribed_text}\n"""\n\nExtract the fields now.',
    }

    try:
        result = await asyncio.to_thread(lambda: structured_llm.invoke([system_message, user_message]))
        parsed: MoodCheckInAnalysisResult = result["parsed"]
        raw = result["raw"]

        meta = getattr(raw, "response_metadata", {}) or {}
        usage = getattr(raw, "usage_metadata", {}) or {}
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        payload = parsed.model_dump()
        if isinstance(payload.get("summary"), str):
            payload["summary"] = _normalize_user_friendly_summary(payload["summary"])

        logger.info("Mood check-in agent completed successfully")
        return AgentResponse.success_response(payload, metadata=metadata)
    except Exception as e:
        logger.error("Mood check-in agent invocation failed", error=str(e))
        return AgentResponse.error_response("Unable to analyze mood at this time.")
