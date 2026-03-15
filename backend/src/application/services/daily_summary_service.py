"""
Service for deterministic context building and LLM daily health summary generation.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.encoders import jsonable_encoder

from ...infrastructure.agents.daily_summary_agent import daily_summary_agent
from ...infrastructure.database.health_models import DailySummary, MealEvent, MedicalConditionSnapshot, VitalEvent
from .health_timeline_service import HealthTimelineService
from .nutrition_target_service import NutritionTargetService


class DailySummaryService:
    @staticmethod
    async def _build_generation_context(db: AsyncSession, user_id: Any, target_date: date) -> Dict[str, Any]:
        # 1. Meals
        meals_result = await db.execute(
            select(MealEvent)
            .where(MealEvent.user_id == user_id, MealEvent.meal_date == target_date)
        )
        meals = meals_result.scalars().all()
        
        # 2. Nutrition Target and Adherence
        try:
            adherence_response = await NutritionTargetService.get_adherence_for_date(db, user_id, target_date)
            # Calculate a simple 0-100 adherence score based on calories
            cal_percent = adherence_response.get("adherence", {}).get("calories_kcal", {}).get("percent", 0)
            if cal_percent is not None:
                # 100% adherence = 100 score. If they are over, subtract the diff.
                diff = abs(100 - cal_percent)
                adherence_score = max(0, 100 - int(diff))
            else:
                adherence_score = 0
        except ValueError:
            adherence_response = {}
            adherence_score = 0
            
        # 3. Vitals
        vitals_result = await db.execute(
            select(VitalEvent).where(VitalEvent.user_id == user_id)
        )
        all_vitals = vitals_result.scalars().all()
        day_vitals = [v for v in all_vitals if v.captured_at.date() == target_date]

        # 4. Conditions
        snapshot_result = await db.execute(
            select(MedicalConditionSnapshot)
            .where(
                MedicalConditionSnapshot.user_id == user_id,
                MedicalConditionSnapshot.is_current.is_(True),
            )
        )
        snapshots = snapshot_result.scalars().all()
        conditions_snapshot = HealthTimelineService._merge_current_snapshots(snapshots)

        return {
            "target_date": target_date.isoformat(),
            "meals": [
                {
                    "type": m.meal_type,
                    "calories": m.total_calories,
                    "protein": m.total_protein_g,
                    "time": m.meal_time.isoformat()
                } for m in meals
            ],
            "vitals": [
                {
                    "type": v.vital_type,
                    "primary": v.value_primary,
                    "unit": v.unit,
                } for v in day_vitals
            ],
            "adherence_score": adherence_score,
            "adherence_details": adherence_response,
            "conditions_snapshot": conditions_snapshot,
        }

    @classmethod
    async def generate_summary(
        cls, db: AsyncSession, user_id: Any, target_date: date
    ) -> Optional[Dict[str, Any]]:
        # Check if already exists
        existing = await cls.get_summary(db, user_id, target_date)
        if existing:
            # We could optionally overwrite, but for now just return existing
            return existing

        context = await cls._build_generation_context(db, user_id, target_date)
        
        # Minimum data check (skip LLM if 0 meals and 0 vitals)
        if not context["meals"] and not context["vitals"]:
            return None
            
        agent_response = await daily_summary_agent(context)
        if not agent_response.success:
            raise ValueError(agent_response.error_message)
            
        summary_data = agent_response.data
        
        # Save to database
        row = DailySummary(
            user_id=user_id,
            summary_date=target_date,
            narrative=summary_data.get("narrative", ""),
            stats_snapshot=jsonable_encoder(context),
            adherence_score=context["adherence_score"],
            alerts=summary_data.get("alerts", []),
            data_quality="sufficient" if (len(context["meals"]) > 0 and len(context["vitals"]) > 0) else "sparse"
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        
        return cls._serialize_summary(row)

    @staticmethod
    async def get_summary(db: AsyncSession, user_id: Any, target_date: date) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(DailySummary)
            .where(DailySummary.user_id == user_id, DailySummary.summary_date == target_date)
        )
        row = result.scalars().first()
        if not row:
            return None
        return DailySummaryService._serialize_summary(row)

    @staticmethod
    async def get_recent_summaries(db: AsyncSession, user_id: Any, limit: int = 7) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(DailySummary)
            .where(DailySummary.user_id == user_id)
            .order_by(DailySummary.summary_date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [DailySummaryService._serialize_summary(row) for row in rows]

    @staticmethod
    def _serialize_summary(summary: DailySummary) -> Dict[str, Any]:
        return {
            "summary_id": str(summary.id),
            "summary_date": summary.summary_date.isoformat(),
            "narrative": summary.narrative,
            "stats_snapshot": summary.stats_snapshot,
            "adherence_score": summary.adherence_score,
            "alerts": summary.alerts,
            "data_quality": summary.data_quality,
            "generated_at": summary.generated_at.isoformat(),
        }
