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

MAX_NARRATIVE_WORDS = 120


def _normalize_narrative(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value
    value = re.sub(r"(?i)\\bthe user\\b", "you", value)
    value = re.sub(r"(?i)\\byou are\\b", "you're", value)
    value = re.sub(r"\\s+", " ", value).strip()
    words = value.split()
    if len(words) > MAX_NARRATIVE_WORDS:
        value = " ".join(words[:MAX_NARRATIVE_WORDS]).rstrip(" .") + "."
    return value


def _format_vitals_for_prompt(vitals: List[Dict]) -> str:
    if not vitals:
        return "No vitals logged today."
    
    lines = []
    for v in vitals:
        vtype = v.get("type", "unknown")
        primary = v.get("value_primary")
        secondary = v.get("value_secondary")
        unit = v.get("unit", "")
        time = v.get("time", "")
        
        if vtype in ["blood_pressure", "bp"] and primary and secondary:
            lines.append(f"  - Blood Pressure: {int(primary)}/{int(secondary)} mmHg at {time}")
        elif vtype in ["blood_glucose", "glucose", "blood_sugar"] and primary:
            lines.append(f"  - Blood Glucose: {primary} {unit} at {time}")
        elif vtype in ["heart_rate", "pulse"] and primary:
            lines.append(f"  - Heart Rate: {int(primary)} {unit} at {time}")
        elif vtype in ["weight"] and primary:
            lines.append(f"  - Weight: {primary} {unit} at {time}")
        elif vtype in ["spo2", "oxygen_saturation"] and primary:
            lines.append(f"  - SpO2: {primary}{unit} at {time}")
        elif primary:
            lines.append(f"  - {vtype}: {primary} {unit} at {time}")
    
    return "\n".join(lines) if lines else "No vitals logged today."


def _format_meals_for_prompt(meals: List[Dict]) -> str:
    if not meals:
        return "No meals logged today."
    
    lines = []
    for m in meals:
        mtype = m.get("type", "meal")
        calories = m.get("calories", 0)
        protein = m.get("protein_g", 0)
        time = m.get("time", "")
        lines.append(f"  - {mtype.capitalize()}: {calories} kcal, {protein}g protein at {time}")
    
    return "\n".join(lines)


def _format_conditions_for_prompt(conditions: Dict) -> str:
    if not conditions:
        return "No health conditions on file."
    
    parts = []
    if conditions.get("diabetes_status") and conditions["diabetes_status"] not in ["unknown", "no"]:
        parts.append(f"Diabetes: {conditions['diabetes_status']}")
    if conditions.get("hypertension_status") and conditions["hypertension_status"] not in ["unknown", "no"]:
        parts.append(f"Hypertension: {conditions['hypertension_status']}")
    if conditions.get("kidney_disease_stage"):
        parts.append(f"Kidney Disease Stage: {conditions['kidney_disease_stage']}")
    if conditions.get("dyslipidemia_status") and conditions["dyslipidemia_status"] not in ["unknown", "no"]:
        parts.append(f"Dyslipidemia: {conditions['dyslipidemia_status']}")
    if conditions.get("allergies"):
        parts.append(f"Allergies: {', '.join(conditions['allergies'])}")
    if conditions.get("food_restrictions"):
        parts.append(f"Restrictions: {', '.join(conditions['food_restrictions'])}")
    
    return "; ".join(parts) if parts else "No active health conditions."


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

    meals = context.get("meals", []) or []
    vitals = context.get("vitals", []) or []
    nutrition_totals = context.get("nutrition_totals", {})
    conditions = context.get("conditions_snapshot", {})
    
    meals_text = _format_meals_for_prompt(meals)
    vitals_text = _format_vitals_for_prompt(vitals)
    conditions_text = _format_conditions_for_prompt(conditions)

    stats_text = (
        f"DATE: {context.get('target_date')}\n"
        f"ADHERENCE SCORE: {context.get('adherence_score', 0)}/100\n\n"
        f"DAILY NUTRITION TOTALS:\n"
        f"  - Calories: {nutrition_totals.get('calories', 0)} kcal\n"
        f"  - Protein: {nutrition_totals.get('protein_g', 0)}g\n"
        f"  - Carbs: {nutrition_totals.get('carbs_g', 0)}g\n"
        f"  - Fat: {nutrition_totals.get('fat_g', 0)}g\n"
        f"  - Fiber: {nutrition_totals.get('fiber_g', 0)}g\n"
        f"  - Sugar: {nutrition_totals.get('sugar_g', 0)}g\n\n"
        f"MEALS LOGGED ({len(meals)}):\n{meals_text}\n\n"
        f"VITALS LOGGED ({len(vitals)}):\n{vitals_text}\n\n"
        f"HEALTH CONDITIONS:\n{conditions_text}"
    )

    base_system_content = (
        "You are Dr. Sarah Mitchell, a board-certified clinical nutritionist reviewing a patient's daily health data. "
        "Your task is to provide a professional, clinically-relevant daily summary.\n\n"
        "ANALYSIS GUIDELINES:\n"
        "1. VITAL ASSESSMENT: Analyze vitals against the patient's health conditions:\n"
        "   - For diabetic patients: Comment on blood glucose levels and their relation to meals (timing, carb intake)\n"
        "   - For hypertensive patients: Note blood pressure readings and sodium-related observations\n"
        "   - For kidney disease: Consider protein intake relative to stage restrictions\n"
        "   - Flag any abnormal readings (high BP >140/90, high glucose >180 mg/dL, low SpO2 <95%)\n\n"
        "2. NUTRITION ASSESSMENT:\n"
        "   - Evaluate macronutrient balance relative to patient's conditions\n"
        "   - Note fiber adequacy (aim for 25-30g daily)\n"
        "   - Comment on sugar intake for diabetics\n"
        "   - Assess protein adequacy for the patient's age and condition\n\n"
        "3. MEAL-VITAL CORRELATIONS:\n"
        "   - If post-meal glucose readings available, note meal impact\n"
        "   - Consider timing of meals relative to medications if relevant\n\n"
        "OUTPUT REQUIREMENTS:\n"
        "- `narrative` (max 120 words): Professional clinical summary with:\n"
        "  * Brief overview of the day's nutrition and vitals\n"
        "  * ONE specific insight connecting data to their health conditions\n"
        "  * ONE or TWO actionable recommendations for tomorrow\n"
        "- `alerts`: List any critical values or concerning patterns requiring attention\n"
        "- Speak directly to the patient using 'you' (never 'the user')\n"
        "- No greetings, no disclaimers - focus on actionable clinical guidance\n"
        "- If data is sparse, briefly note what should be tracked"
    )
    
    system_message = {
        "role": "system",
        "content": base_system_content,
    }

    user_content = f"Analyze today's health data and provide a clinical summary:\n\n{stats_text}"
    
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
