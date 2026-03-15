import asyncio
import time
from typing import Any, Dict, List
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
from ...presentation.schemas.diet_plan_schemas import DietPlanMealSchema


class DietPlanGenerationResult(BaseModel):
    notes: str = Field(description="Reasoning and general advice for the plan")
    meals: List[DietPlanMealSchema] = Field(
        default_factory=list, 
        description="List of meals for the 7-day plan, covering 0=Monday through 6=Sunday"
    )

async def diet_plan_agent(context: Dict[str, Any]) -> AgentResponse:
    """
    Generate a 7-day diet plan based on the user's health context.
    """
    started_at = time.perf_counter()
    agent_name = "diet_plan_agent"
    logger.info("Diet plan agent invoked", context_keys=list(context.keys()))

    try:
        llm_settings = get_agent_llm_config(agent_name)
        diagnostics = get_chat_model_diagnostics(agent_name=agent_name, **llm_settings)
        logger.info("Diet plan agent model config", **diagnostics)
        llm = create_llm(agent_name=agent_name, temperature=0.0, **llm_settings)
        structured_llm = llm.with_structured_output(DietPlanGenerationResult, include_raw=True)
    except Exception as e:
        logger.error(
            "Diet plan agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
        )
        return AgentResponse.error_response("Diet plan generation service is temporarily unavailable.")

    base_system_content = (
        "You are Dr. Sarah Mitchell, a board-certified clinical nutritionist. "
        "Your task is to generate a personalized 7-day diet plan based on the user's health context, conditions, and targets.\n\n"
        "RULES:\n"
        "1. Generate meals for all 7 days (day_of_week 0 to 6 where 0 is Monday) and typical meal types (breakfast, lunch, dinner, snack).\n"
        "2. Ensure the daily total calories across all meals closely matches the daily calorie_target.\n"
        "3. Provide realistic macro breakdowns per food item.\n"
        "4. Follow all safety guards rigidly.\n"
        "5. Output must exactly match the required JSON schema with `notes` and `meals`."
    )

    # Apply safety guards deterministic to prompt
    if context.get("kidney_disease_stage"):
        base_system_content += f"\n[SAFETY GUARD] The user has kidney disease stage {context['kidney_disease_stage']}. Strictly enforce a protein cap."

    if str(context.get("diabetes_status", "")).lower() == "yes":
        base_system_content += "\n[SAFETY GUARD] The user has diabetes. Provide low glycemic index foods."

    if context.get("allergies"):
        base_system_content += f"\n[SAFETY GUARD] Hard stop on these allergies: {', '.join(context['allergies'])}"

    if context.get("food_restrictions"):
        base_system_content += f"\n[SAFETY GUARD] Hard stop on these restrictions: {', '.join(context['food_restrictions'])}"

    system_message = {
        "role": "system",
        "content": base_system_content,
    }

    user_content = f"Generate a 7-day diet plan based on this context:\n{context}\n\nReturn the structured meals and notes."

    message = {
        "role": "user",
        "content": user_content,
    }

    try:
        if is_llm_debug_enabled(agent_name):
            logger.debug(
                "Diet plan agent LLM request payload",
                agent_name=agent_name,
                llm_messages=build_llm_debug_payload([system_message, message], agent_name=agent_name),
            )

        invoke_started_at = time.perf_counter()
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )
        invoke_duration_ms = round((time.perf_counter() - invoke_started_at) * 1000, 2)

        parsed: DietPlanGenerationResult = result["parsed"]
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
            "Diet plan agent completed successfully",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            invoke_duration_ms=invoke_duration_ms,
            meal_count=len(structured_data.get("meals", [])),
            token_usage=usage,
        )
        return AgentResponse.success_response(structured_data, metadata=metadata)

    except Exception as e:
        logger.error(
            "Diet plan agent invocation failed",
            error=str(e),
            exception_type=type(e).__name__,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return AgentResponse.error_response("Unable to generate diet plan at this time.")
