"""
Pure meal/vital association heuristics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


VITAL_WINDOWS = {
    "cgm": (30, 180, 20),
    "glucose": (30, 180, 20),
    "blood_pressure": (30, 240, 15),
    "bp": (30, 240, 15),
    "heart_rate": (15, 120, 20),
}


def collect_context_factors(mood_checkins: List[Dict[str, Any]], meal_time: datetime) -> List[str]:
    factors = []
    for checkin in mood_checkins:
        captured_at = datetime.fromisoformat(checkin["captured_at"])
        delta_minutes = abs((captured_at - meal_time).total_seconds() / 60)
        if delta_minutes > 360:
            continue
        if (checkin.get("stress_level") or 0) >= 4:
            factors.append("stress")
        if checkin.get("sleep_quality") is not None and checkin["sleep_quality"] <= 2:
            factors.append("poor sleep")
    return sorted(set(factors))


def compute_associations_payload(
    meals: List[Dict[str, Any]],
    vitals: List[Dict[str, Any]],
    mood_checkins: List[Dict[str, Any]],
    health_profile: Dict[str, Any],
) -> Dict[str, Any]:
    associations = []
    factors = set()

    for meal in meals:
        meal_time = datetime.fromisoformat(meal["meal_time"])
        carbs = meal.get("total_carbohydrates_g") or 0
        for vital in vitals:
            vital_type = vital["vital_type"].lower()
            if vital_type not in VITAL_WINDOWS:
                continue

            captured_at = datetime.fromisoformat(vital["captured_at"])
            delta_minutes = (captured_at - meal_time).total_seconds() / 60
            window_start, window_end, threshold = VITAL_WINDOWS[vital_type]
            if delta_minutes < window_start or delta_minutes > window_end:
                continue

            baseline_candidates = [
                candidate["value_primary"]
                for candidate in vitals
                if candidate["vital_type"].lower() == vital_type
                and datetime.fromisoformat(candidate["captured_at"]) < meal_time
            ]
            baseline = sum(baseline_candidates[-5:]) / len(baseline_candidates[-5:]) if baseline_candidates else vital["value_primary"]
            delta_value = vital["value_primary"] - baseline
            if delta_value < threshold:
                continue

            insight_factors = []
            if vital_type in {"cgm", "glucose"} and carbs >= 40:
                insight_factors.append("meal carb load")
            insight_factors.extend(collect_context_factors(mood_checkins, meal_time))

            report_snapshot = health_profile.get("snapshot", {})
            if report_snapshot.get("diabetes_status") == "yes" and vital_type in {"cgm", "glucose"}:
                insight_factors.append("current diabetes context")
            if health_profile.get("medications"):
                insight_factors.append("medication timing")

            unique_factors = sorted(set(insight_factors))
            factors.update(unique_factors)
            confidence = "medium" if delta_value >= threshold * 1.5 else "low"
            associations.append(
                {
                    "meal_id": meal["id"],
                    "vital_id": vital["id"],
                    "meal_time": meal["meal_time"],
                    "vital_time": vital["captured_at"],
                    "vital_type": vital["vital_type"],
                    "confidence_tier": confidence,
                    "association_label": f"{vital['vital_type']} spike after {meal['meal_type']}",
                    "explanation": (
                        f"This spike may be associated with the {meal['meal_type']} meal at "
                        f"{meal_time.strftime('%H:%M')}. {vital['vital_type']} increased by "
                        f"{round(delta_value, 1)} {vital['unit']} about {int(delta_minutes)} minutes later."
                    ),
                    "possible_factors": unique_factors,
                    "evidence": {
                        "baseline": round(baseline, 2),
                        "observed": vital["value_primary"],
                        "delta": round(delta_value, 2),
                        "minutes_after_meal": int(delta_minutes),
                    },
                }
            )

    return {
        "associations": associations,
        "possible_factors": sorted(factors),
    }


def build_correlation_narrative(period_label: str, associations: List[Dict[str, Any]]) -> str:
    if not associations:
        return (
            f"No strong meal-linked spikes were detected in this {period_label} window. "
            "Continue collecting meals and vitals to improve association quality."
        )

    first = associations[0]
    factor_text = ", ".join(first["possible_factors"]) if first["possible_factors"] else "meal timing and current health context"
    return (
        f"{len(associations)} possible associations were detected in this {period_label} window. "
        f"The strongest current signal is that a {first['vital_type']} spike may be associated with a recent meal. "
        f"Possible contributing factors: {factor_text}."
    )
