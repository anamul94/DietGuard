from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DailySummaryCreate(BaseModel):
    summary_date: str = Field(description="YYYY-MM-DD")


class DailySummaryResponse(BaseModel):
    summary_id: str
    summary_date: str
    narrative: str
    stats_snapshot: Dict[str, Any]
    adherence_score: int
    alerts: List[str]
    data_quality: str
    generated_at: str

    class Config:
        from_attributes = True

