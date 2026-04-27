import asyncio
import time
from typing import Dict, Any

from pydantic import BaseModel, Field

from .agent_response import AgentResponse
from ..utils.bedrock_utils import (
    build_llm_debug_payload,
    create_llm,
    get_agent_llm_config,
    get_chat_model_diagnostics,
    is_llm_debug_enabled,
)
from ..utils.logger import logger


class DietChartExtraction(BaseModel):
    medical_condition: str | None = Field(
        default=None,
        description="Detected medical condition (diabetes, hypertension, kidney disease, etc.)"
    )
    avoid_foods: list[str] = Field(
        default_factory=list,
        description="Foods to completely avoid (sugar, fried food, red meat)"
    )
    limit_foods: list[str] = Field(
        default_factory=list,
        description="Foods to limit/restrict portions (rice, salt, carbs)"
    )
    allowed_foods: list[str] = Field(
        default_factory=list,
        description="Recommended/allowed foods (vegetables, lean protein)"
    )
    meal_frequency: int | None = Field(
        default=3,
        description="Number of meals per day recommended"
    )
    calorie_limit: int | None = Field(
        default=None,
        description="Daily calorie limit if specified"
    )
    salt_limit: str | None = Field(
        default=None,
        description="Salt restriction level (low sodium, no added salt)"
    )
    doctor_notes: str | None = Field(
        default=None,
        description="Additional notes from doctor/dietitian"
    )
    extraction_confidence: str = Field(
        default="high",
        description="Confidence level: high/medium/low"
    )
    unreadable_sections: list[str] = Field(
        default_factory=list,
        description="Parts that couldn't be clearly read"
    )


async def diet_chart_agent(
    data: str,
    file_type: str,
    mime_type: str,
    raw_text: str | None = None
) -> AgentResponse:
    """
    Parse doctor's diet charts, prescriptions, and nutritionist recommendations.
    
    Extracts structured diet restrictions from:
    - Diet charts from doctors/dietitians
    - Nutritionist meal plans
    - Medical prescriptions with dietary advice
    - Handwritten diet instructions
    
    Args:
        data: base64-encoded string of the file/image
        file_type: "image" | "file" | "text"
        mime_type: e.g. "image/jpeg" or "application/pdf"
        raw_text: Optional pre-extracted text (for manual entry)
    
    Returns:
        AgentResponse with DietChartExtraction JSON data
    """
    started_at = time.perf_counter()
    agent_name = "diet_chart_agent"
    logger.info("Diet chart agent invoked", file_type=file_type, mime_type=mime_type)
    
    if file_type not in ("image", "file", "text"):
        return AgentResponse.error_response(
            "This service only accepts image files, PDF documents, or text input. "
            "Please upload a diet chart or prescription."
        )
    
    allowed_mime_types = ("image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain")
    if file_type != "text" and mime_type not in allowed_mime_types:
        return AgentResponse.error_response(
            f"Unsupported file type: {mime_type}. "
            "Please upload a diet chart as JPEG, PNG, WebP, PDF, or enter text manually."
        )
    
    try:
        llm_settings = get_agent_llm_config(agent_name)
        diagnostics = get_chat_model_diagnostics(agent_name=agent_name, **llm_settings)
        logger.info("Diet chart agent model config", **diagnostics)
        llm = create_llm(agent_name=agent_name, temperature=0.0, **llm_settings)
        structured_llm = llm.with_structured_output(DietChartExtraction, include_raw=True)
    except Exception as e:
        logger.error(
            "Diet chart agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
        )
        return AgentResponse.error_response("Diet chart extraction service is temporarily unavailable.")
    
    system_content = (
        "CRITICAL: All your responses must be in English only. No other language is permitted.\n\n"
        "You are a clinical nutrition assistant that extracts diet restrictions from "
        "doctor's diet charts, prescriptions, and nutritionist recommendations.\n\n"
        "CRITICAL: You must output ONLY structured diet data, NOT medical advice.\n\n"
        "ACCEPTED DOCUMENT TYPES:\n"
        "- Diet charts from doctors or dietitians\n"
        "- Nutritionist meal plans and recommendations\n"
        "- Medical prescriptions with dietary advice\n"
        "- Handwritten diet instructions\n"
        "- Food restriction lists\n"
        "- Meal timing guidelines\n"
        "\n"
        "REJECTED CONTENT (return with extraction_confidence='none' and explain in doctor_notes):\n"
        "- General medical reports (lab results, X-rays) - these are handled by another system\n"
        "- Non-diet/non-food related documents\n"
        "- Random images not related to diet\n"
        "\n"
        "EXTRACTION RULES:\n"
        "1. Extract foods to AVOID completely (sugar, fried food, red meat, alcohol, etc.)\n"
        "2. Extract foods to LIMIT or restrict portions (rice, salt, carbohydrates, etc.)\n"
        "3. Extract foods that are ALLOWED or recommended (vegetables, lean protein, whole grains)\n"
        "4. Identify any medical condition mentioned (diabetes, hypertension, kidney disease, pregnancy, etc.)\n"
        "5. Note meal frequency recommendations (e.g., '5 small meals per day')\n"
        "6. Extract calorie limits if specified\n"
        "7. Note salt/sodium restrictions\n"
        "8. Capture any additional doctor notes\n"
        "\n"
        "CONFIDENCE LEVELS:\n"
        "- 'high': Document is clearly a diet chart with legible instructions\n"
        "- 'medium': Document appears to be diet-related but some parts are unclear\n"
        "- 'low': Document may be diet-related but extraction is uncertain\n"
        "- 'none': Document is not diet-related or completely illegible\n"
        "\n"
        "IMPORTANT:\n"
        "- Do NOT diagnose conditions - only extract what is explicitly written\n"
        "- Do NOT add medical advice beyond what's in the document\n"
        "- If the document mentions 'low sodium', 'no added salt', etc., include in salt_limit\n"
        "- Preserve exact food names as written\n"
        "- If meal frequency is not specified, leave as null\n"
    )
    
    system_message = {
        "role": "system",
        "content": system_content,
    }
    
    user_content = "Extract all diet restrictions and food guidelines from this document into the structured format."
    
    if file_type == "text" and raw_text:
        message = {
            "role": "user",
            "content": f"{user_content}\n\nDocument text:\n{raw_text}",
        }
    elif file_type == "file" and mime_type == "application/pdf":
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_content},
                {
                    "type": "document",
                    "source": {
                        "bytes": data
                    },
                    "format": "pdf",
                    "name": "diet_chart"
                },
            ],
        }
    else:
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_content},
                {
                    "type": "image",
                    "source": {
                        "bytes": data
                    },
                    "format": mime_type.split("/")[-1] if "/" in mime_type else "jpeg",
                },
            ],
        }
    
    try:
        if is_llm_debug_enabled(agent_name):
            logger.debug(
                "Diet chart agent LLM request payload",
                agent_name=agent_name,
                llm_messages=build_llm_debug_payload([system_message, message], agent_name=agent_name),
            )
        
        invoke_started_at = time.perf_counter()
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )
        invoke_duration_ms = round((time.perf_counter() - invoke_started_at) * 1000, 2)
        
        parsed: DietChartExtraction = result["parsed"]
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
        
        logger.info(
            "Diet chart agent completed successfully",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            invoke_duration_ms=invoke_duration_ms,
            extraction_confidence=structured_data.get("extraction_confidence"),
            avoid_count=len(structured_data.get("avoid_foods", [])),
            limit_count=len(structured_data.get("limit_foods", [])),
            token_usage=usage,
        )
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
    
    except Exception as e:
        logger.error(
            "Diet chart agent invocation failed",
            error=str(e),
            exception_type=type(e).__name__,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return AgentResponse.error_response("Unable to extract diet restrictions at this time.")
