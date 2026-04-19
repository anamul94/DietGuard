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
        meals_result = await db.execute(
            select(MealEvent)
            .where(MealEvent.user_id == user_id, MealEvent.meal_date == target_date)
        )
        meals = meals_result.scalars().all()
        
        try:
            adherence_response = await NutritionTargetService.get_adherence_for_date(db, user_id, target_date)
            cal_percent = adherence_response.get("adherence", {}).get("calories_kcal", {}).get("percent", 0)
            if cal_percent is not None:
                diff = abs(100 - cal_percent)
                adherence_score = max(0, 100 - int(diff))
            else:
                adherence_score = 0
        except ValueError:
            adherence_response = {}
            adherence_score = 0
            
        vitals_result = await db.execute(
            select(VitalEvent).where(VitalEvent.user_id == user_id)
        )
        all_vitals = vitals_result.scalars().all()
        day_vitals = [v for v in all_vitals if v.captured_at.date() == target_date]

        snapshot_result = await db.execute(
            select(MedicalConditionSnapshot)
            .where(
                MedicalConditionSnapshot.user_id == user_id,
                MedicalConditionSnapshot.is_current.is_(True),
            )
        )
        snapshots = snapshot_result.scalars().all()
        conditions_snapshot = HealthTimelineService._merge_current_snapshots(snapshots)

        total_protein = sum(float(m.total_protein_g or 0) for m in meals)
        total_carbs = sum(float(m.total_carbohydrates_g or 0) for m in meals)
        total_fat = sum(float(m.total_fat_g or 0) for m in meals)
        total_fiber = sum(float(m.total_fiber_g or 0) for m in meals)
        total_sugar = sum(float(m.total_sugar_g or 0) for m in meals)

        return {
            "target_date": target_date.isoformat(),
            "meals": [
                {
                    "type": m.meal_type,
                    "calories": m.total_calories,
                    "protein_g": float(m.total_protein_g) if m.total_protein_g else 0,
                    "carbs_g": float(m.total_carbohydrates_g) if m.total_carbohydrates_g else 0,
                    "fat_g": float(m.total_fat_g) if m.total_fat_g else 0,
                    "time": m.meal_time.strftime("%H:%M") if m.meal_time else None,
                    "items": m.items if hasattr(m, 'items') else [],
                } for m in meals
            ],
            "nutrition_totals": {
                "calories": sum(m.total_calories for m in meals),
                "protein_g": round(total_protein, 1),
                "carbs_g": round(total_carbs, 1),
                "fat_g": round(total_fat, 1),
                "fiber_g": round(total_fiber, 1),
                "sugar_g": round(total_sugar, 1),
            },
            "vitals": [
                {
                    "type": v.vital_type,
                    "value_primary": float(v.value_primary) if v.value_primary else None,
                    "value_secondary": float(v.value_secondary) if v.value_secondary else None,
                    "unit": v.unit,
                    "time": v.captured_at.strftime("%H:%M") if v.captured_at else None,
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
