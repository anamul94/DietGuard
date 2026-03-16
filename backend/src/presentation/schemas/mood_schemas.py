from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MoodCheckInResponse(BaseModel):
    mood_checkin_id: str
    user_id: str
    session_id: str

    captured_at: datetime
    analyzed_at: datetime
    user_local_time: datetime
    time_of_day: Literal["morning", "afternoon", "evening", "night"]
    day_of_week: str
    transcript: str

    primary_emotion: str
    secondary_emotions: List[str] = Field(default_factory=list)
    stress_level: int = Field(ge=0, le=100)
    key_stress_indicators: List[str] = Field(default_factory=list)
    urgency_level: Literal["low", "medium", "high"]
    summary: str


class MoodHistoryItem(BaseModel):
    mood_checkin_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    captured_at: datetime
    analyzed_at: Optional[datetime] = None
    user_local_time: Optional[datetime] = None
    time_of_day: Optional[Literal["morning", "afternoon", "evening", "night"]] = None
    day_of_week: Optional[str] = None
    transcript: Optional[str] = None

    primary_emotion: Optional[str] = None
    secondary_emotions: List[str] = Field(default_factory=list)
    stress_level: Optional[int] = Field(default=None, ge=0, le=100)
    key_stress_indicators: List[str] = Field(default_factory=list)
    urgency_level: Optional[Literal["low", "medium", "high"]] = None
    summary: Optional[str] = None

    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw stored symptom_flags for forward compatibility")


class PaginatedMoodHistoryResponse(BaseModel):
    items: List[MoodHistoryItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
