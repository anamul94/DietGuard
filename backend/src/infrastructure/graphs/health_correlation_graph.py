"""
LangGraph workflow for meal/vital correlation summaries.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .health_correlation import build_correlation_narrative, compute_associations_payload


class CorrelationState(TypedDict):
    meals: List[Dict[str, Any]]
    vitals: List[Dict[str, Any]]
    mood_checkins: List[Dict[str, Any]]
    health_profile: Dict[str, Any]
    period_label: str
    associations: List[Dict[str, Any]]
    possible_factors: List[str]
    narrative: str


def compute_associations(state: CorrelationState) -> Dict[str, Any]:
    return compute_associations_payload(
        meals=state["meals"],
        vitals=state["vitals"],
        mood_checkins=state["mood_checkins"],
        health_profile=state["health_profile"],
    )


def build_narrative(state: CorrelationState) -> Dict[str, Any]:
    return {
        "narrative": build_correlation_narrative(
            period_label=state["period_label"],
            associations=state.get("associations", []),
        )
    }


_builder = StateGraph(CorrelationState)
_builder.add_node("compute_associations", compute_associations)
_builder.add_node("build_narrative", build_narrative)
_builder.add_edge(START, "compute_associations")
_builder.add_edge("compute_associations", "build_narrative")
_builder.add_edge("build_narrative", END)
HEALTH_CORRELATION_GRAPH = _builder.compile()


def summarize_health_period(
    meals: List[Dict[str, Any]],
    vitals: List[Dict[str, Any]],
    mood_checkins: List[Dict[str, Any]],
    health_profile: Dict[str, Any],
    period_label: str,
) -> Dict[str, Any]:
    return HEALTH_CORRELATION_GRAPH.invoke(
        {
            "meals": meals,
            "vitals": vitals,
            "mood_checkins": mood_checkins,
            "health_profile": health_profile,
            "period_label": period_label,
            "associations": [],
            "possible_factors": [],
            "narrative": "",
        }
    )
