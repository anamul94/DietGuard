"""
Service for deterministic context building and LLM plan generation.
"""

from datetime import date, timedelta
import time
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...infrastructure.agents.diet_plan_agent import diet_plan_agent
from ...infrastructure.database.health_models import DietPlan, DietPlanMeal
from ...infrastructure.database.patient_models import PatientPersona
from ...infrastructure.utils.logger import logger
from .health_timeline_service import HealthTimelineService
from .nutrition_target_service import NutritionTargetService


class DietPlanService:
    MACRO_FIELDS = ("calories_kcal", "protein_g", "carbohydrates_g", "fat_g", "fiber_g")

    @staticmethod
    def _normalize_macro_targets(values: Mapping[str, Any]) -> Dict[str, float]:
        return {
            field: float(values.get(field) or 0)
            for field in DietPlanService.MACRO_FIELDS
        }
    @staticmethod
    async def _build_generation_context(db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        patient_result = await db.execute(select(PatientPersona).where(PatientPersona.user_id == user_id))
        persona = patient_result.scalar_one_or_none()
        
        health_profile = await HealthTimelineService.get_current_health_profile(db, user_id)
        current_target = await NutritionTargetService.get_current_target(db, user_id)
        
        if not current_target:
            current_target = await NutritionTargetService.upsert_calculated_target(db, user_id)
            
        snapshot = health_profile.get("snapshot", {})
        
        age = None
        if persona and persona.date_of_birth:
            today = date.today()
            age = today.year - persona.date_of_birth.year - ((today.month, today.day) < (persona.date_of_birth.month, persona.date_of_birth.day))

        return {
            "age": age,
            "gender": persona.gender if persona else None,
            "weight_kg": float(persona.weight_kg) if persona and persona.weight_kg else None,
            "height_cm": float(persona.height_cm) if persona and persona.height_cm else None,
            "activity_level": persona.activity_level if persona else "sedentary",
            "birth_place": persona.birth_place if persona else None,
            "nationality": persona.nationality if persona else None,
            "current_location": persona.current_location if persona else None,
            "diabetes_status": snapshot.get("diabetes_status", "unknown"),
            "hypertension_status": snapshot.get("hypertension_status", "unknown"),
            "kidney_disease_stage": snapshot.get("kidney_disease_stage"),
            "dyslipidemia_status": snapshot.get("dyslipidemia_status", "unknown"),
            "allergies": snapshot.get("allergies", []),
            "food_restrictions": snapshot.get("food_restrictions", []),
            "dietary_preferences": snapshot.get("dietary_preferences", []),
            "active_medications": [
                {
                    "name": med.get("medication_name"),
                    "schedule": med.get("schedule"),
                    "with_food": med.get("with_food")
                }
                for med in health_profile.get("medications", [])
            ],
            "calorie_target": current_target.get("calories_kcal", 2000),
            "macro_targets": {
                "protein_g": current_target.get("protein_g", 0),
                "carbohydrates_g": current_target.get("carbohydrates_g", 0),
                "fat_g": current_target.get("fat_g", 0),
                "fiber_g": current_target.get("fiber_g", 0),
            },
        }

    @staticmethod
    def _macro_targets_from_context(context: Dict[str, Any]) -> Dict[str, float]:
        macro = context.get("macro_targets", {})
        combined = {
            "calories_kcal": context.get("calorie_target", 0),
            "protein_g": macro.get("protein_g", 0),
            "carbohydrates_g": macro.get("carbohydrates_g", 0),
            "fat_g": macro.get("fat_g", 0),
            "fiber_g": macro.get("fiber_g", 0),
        }
        return DietPlanService._normalize_macro_targets(combined)

    @staticmethod
    async def _resolve_macro_targets(db: AsyncSession, user_id: Any) -> Dict[str, float]:
        current_target = await NutritionTargetService.get_current_target(db, user_id)
        if not current_target:
            current_target = await NutritionTargetService.upsert_calculated_target(db, user_id)
        return DietPlanService._normalize_macro_targets(
            {
                "calories_kcal": current_target.get("calories_kcal", 0),
                "protein_g": current_target.get("protein_g", 0),
                "carbohydrates_g": current_target.get("carbohydrates_g", 0),
                "fat_g": current_target.get("fat_g", 0),
                "fiber_g": current_target.get("fiber_g", 0),
            }
        )

    @staticmethod
    async def deactivate_active_plans(db: AsyncSession, user_id: Any) -> None:
        await db.execute(
            update(DietPlan)
            .where(DietPlan.user_id == user_id, DietPlan.is_active.is_(True))
            .values(is_active=False)
        )

    @classmethod
    async def generate_diet_plan(
        cls, db: AsyncSession, user_id: Any, trigger: str = "manual"
    ) -> Dict[str, Any]:
        started_at = time.perf_counter()
        logger.info("Diet plan generation started", user_id=str(user_id), trigger=trigger)

        context_started_at = time.perf_counter()
        context = await cls._build_generation_context(db, user_id)
        logger.info(
            "Diet plan context built",
            user_id=str(user_id),
            trigger=trigger,
            duration_ms=round((time.perf_counter() - context_started_at) * 1000, 2),
            context_keys=list(context.keys()),
        )
        calorie_target = context["calorie_target"]
        
        agent_started_at = time.perf_counter()
        agent_response = await diet_plan_agent(context)
        logger.info(
            "Diet plan agent finished",
            user_id=str(user_id),
            trigger=trigger,
            success=agent_response.success,
            duration_ms=round((time.perf_counter() - agent_started_at) * 1000, 2),
            metadata=agent_response.metadata,
        )
        if not agent_response.success:
            raise ValueError(agent_response.error_message)
            
        plan_data = agent_response.data
        
        await cls.deactivate_active_plans(db, user_id)
        
        today = date.today()
        plan = DietPlan(
            user_id=user_id,
            valid_from=today,
            # 7-day plan inclusive of valid_from (today .. today+6)
            valid_until=today + timedelta(days=6),
            generated_by="diet_plan_agent_v1",
            trigger=trigger,
            calorie_target=calorie_target,
            notes=plan_data.get("notes"),
            is_active=True
        )
        db.add(plan)
        await db.flush()
        
        for meal_dtm in plan_data.get("meals", []):
            meal = DietPlanMeal(
                diet_plan_id=plan.id,
                day_of_week=meal_dtm.get("day_of_week", 0),
                meal_type=meal_dtm.get("meal_type", "snack"),
                meal_name=meal_dtm.get("meal_name", ""),
                description=meal_dtm.get("description"),
                foods=meal_dtm.get("foods", []),
                total_calories=meal_dtm.get("total_calories", 0),
                total_protein_g=meal_dtm.get("total_protein_g", 0),
                notes=meal_dtm.get("notes")
            )
            db.add(meal)
            
        await db.commit()
        await db.refresh(plan)
        logger.info(
            "Diet plan persisted",
            user_id=str(user_id),
            trigger=trigger,
            meal_count=len(plan_data.get("meals", [])),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return await cls.get_plan_by_id(db, plan.id)

    @staticmethod
    async def get_current_plan(db: AsyncSession, user_id: Any) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(DietPlan)
            .options(selectinload(DietPlan.meals))
            .where(DietPlan.user_id == user_id, DietPlan.is_active.is_(True))
            .order_by(DietPlan.created_at.desc())
            .limit(1)
        )
        plan = result.scalars().first()
        if not plan:
            return None
        macro_targets = await DietPlanService._resolve_macro_targets(db, user_id)
        return DietPlanService._serialize_plan(plan, macro_targets=macro_targets)

    @staticmethod
    async def get_plan_by_id(db: AsyncSession, plan_id: Any) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(DietPlan)
            .options(selectinload(DietPlan.meals))
            .where(DietPlan.id == plan_id)
        )
        plan = result.scalars().first()
        if not plan:
            return None
        macro_targets = await DietPlanService._resolve_macro_targets(db, plan.user_id)
        return DietPlanService._serialize_plan(plan, macro_targets=macro_targets)

    @staticmethod
    def _serialize_plan(plan: DietPlan, macro_targets: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
        return {
            "plan_id": str(plan.id),
            "valid_from": plan.valid_from.isoformat(),
            "valid_until": plan.valid_until.isoformat(),
            "generated_by": plan.generated_by,
            "trigger": plan.trigger,
            "calorie_target": plan.calorie_target,
            "macro_targets": DietPlanService._normalize_macro_targets(macro_targets or {}),
            "notes": plan.notes,
            "is_active": plan.is_active,
            "meals": [
                {
                    "day_of_week": meal.day_of_week,
                    "meal_type": meal.meal_type,
                    "meal_name": meal.meal_name,
                    "description": meal.description,
                    "foods": meal.foods,
                    "total_calories": meal.total_calories,
                    "total_protein_g": float(meal.total_protein_g),
                    "notes": meal.notes
                }
                for meal in sorted(plan.meals, key=lambda m: (m.day_of_week, ["breakfast", "lunch", "snack", "dinner"].index(m.meal_type) if m.meal_type in ["breakfast", "lunch", "snack", "dinner"] else 99))
            ]
        }
        
    @staticmethod
    async def get_plan_history(db: AsyncSession, user_id: Any) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(DietPlan)
            .options(selectinload(DietPlan.meals))
            .where(DietPlan.user_id == user_id)
            .order_by(DietPlan.created_at.desc())
        )
        plans = result.scalars().all()
        macro_targets = await DietPlanService._resolve_macro_targets(db, user_id)
        return [
            DietPlanService._serialize_plan(plan, macro_targets=macro_targets)
            for plan in plans
        ]
        
    @staticmethod
    async def get_todays_plan_meals(db: AsyncSession, user_id: Any) -> List[Dict[str, Any]]:
        plan = await DietPlanService.get_current_plan(db, user_id)
        if not plan:
            return []
            
        today_wd = date.today().weekday()
        meals_today = [m for m in plan.get("meals", []) if m["day_of_week"] == today_wd]
        return meals_today
