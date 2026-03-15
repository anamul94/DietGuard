"""
Service for comparing medical reports over time.
"""

from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession


class ReportComparisonService:
    @staticmethod
    def classify_trend(current: float, previous: float, canonical_name: str) -> str:
        """
        Classify whether a trend is improving, stable, or worsening based on canonical lab name thresholds.
        """
        if current == previous:
            return "stable"
            
        canonical = (canonical_name or "").lower()
        delta = current - previous
        
        # Lower is better (typically)
        if "hba1c" in canonical or "glucose" in canonical or "ldl" in canonical or "creatinine" in canonical or "triglyceride" in canonical:
            # Worsening = increased significantly
            if "hba1c" in canonical and delta >= 0.3:
                return "worsening"
            if "hba1c" in canonical and delta <= -0.3:
                return "improving"
                
            if "glucose" in canonical and delta >= 10:
                return "worsening"
            if "glucose" in canonical and delta <= -10:
                return "improving"
                
            if "ldl" in canonical and delta >= 10:
                return "worsening"
            if "ldl" in canonical and delta <= -10:
                return "improving"
                
            if "creatinine" in canonical and delta >= 0.2:
                return "worsening"
            if "creatinine" in canonical and delta <= -0.2:
                return "improving"
                
        # Higher is better (typically)
        if "hdl" in canonical:
            if delta <= -5:
                return "worsening"
            if delta >= 5:
                return "improving"
                
        # For general, any change might not be immediately classifiable without more clinical context
        # But we can try to guess or just return stable if delta is small
        pct_change = abs(delta) / float(previous) if previous else 0
        if pct_change < 0.05:
            return "stable"
            
        return "stable"

    @classmethod
    async def evaluate_worsening(cls, db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        """
        Evaluate if any labs have worsened based on recent reports.
        """
        from .health_timeline_service import HealthTimelineService  # lazy to avoid circular import
        profile = await HealthTimelineService.get_current_health_profile(db, user_id)
        lab_trends = profile.get("lab_trends", [])
        
        worsening_labs = []
        for trend in lab_trends:
            direction = cls.classify_trend(
                current=trend["current_value"],
                previous=trend["previous_value"],
                canonical_name=trend["label"],
            )
            # Add the trend_direction so callers can use it 
            trend["trend_direction"] = direction
            if direction == "worsening":
                worsening_labs.append(trend)
                
        return {
            "worsening_detected": len(worsening_labs) > 0,
            "worsening_labs": worsening_labs,
            "all_trends": lab_trends,
        }
