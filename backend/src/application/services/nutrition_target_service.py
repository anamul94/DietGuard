"""
Deterministic nutrition target engine (no LLM dependency).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.health_models import MealEvent, MedicalConditionSnapshot, NutritionTarget
from ...infrastructure.database.patient_models import PatientPersona


class NutritionTargetService:
    ACTIVITY_MULTIPLIERS = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }

    @staticmethod
    def _to_float(value: Any, fallback: float = 0.0) -> float:
        if value is None:
            return fallback
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    @staticmethod
    def _round_metric(value: float) -> float:
        return round(max(0.0, value), 2)

    @staticmethod
    def _extract_kidney_stage(stage_text: Optional[str]) -> Optional[int]:
        if not stage_text:
            return None
        match = re.search(r"(\d+)", stage_text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _status_with_precedence(statuses: list[str]) -> str:
        normalized = [status.lower() for status in statuses if status]
        if "yes" in normalized:
            return "yes"
        if "no" in normalized:
            return "no"
        return "unknown"

    @staticmethod
    def _calculate_age(dob: date) -> int:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @staticmethod
    def _serialize_target(target: NutritionTarget) -> Dict[str, Any]:
        return {
            "target_id": str(target.id),
            "target_date": target.target_date.isoformat(),
            "calories_kcal": target.calories_kcal,
            "protein_g": float(target.protein_g),
            "carbohydrates_g": float(target.carbohydrates_g),
            "fat_g": float(target.fat_g),
            "fiber_g": float(target.fiber_g),
            "source": target.source,
            "calculation_basis": target.calculation_basis or {},
            "is_active": bool(target.is_active),
            "created_at": target.created_at.isoformat() if target.created_at else None,
        }

    @classmethod
    async def _get_condition_context(cls, db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        result = await db.execute(
            select(MedicalConditionSnapshot)
            .where(
                MedicalConditionSnapshot.user_id == user_id,
                MedicalConditionSnapshot.is_current.is_(True),
            )
            .order_by(
                MedicalConditionSnapshot.snapshot_date.desc().nulls_last(),
                MedicalConditionSnapshot.created_at.desc(),
            )
        )
        snapshots = result.scalars().all()
        if not snapshots:
            return {
                "diabetes_status": "unknown",
                "hypertension_status": "unknown",
                "kidney_disease_stage": None,
            }

        diabetes_status = cls._status_with_precedence([snapshot.diabetes_status for snapshot in snapshots])
        hypertension_status = cls._status_with_precedence([snapshot.hypertension_status for snapshot in snapshots])
        stage_values = [snapshot.kidney_disease_stage for snapshot in snapshots if snapshot.kidney_disease_stage]
        best_stage = None
        if stage_values:
            best_stage = max(stage_values, key=lambda value: cls._extract_kidney_stage(value) or 0)

        return {
            "diabetes_status": diabetes_status,
            "hypertension_status": hypertension_status,
            "kidney_disease_stage": best_stage,
        }

    @classmethod
    def _calculate_target_values(cls, persona: PatientPersona, conditions: Dict[str, Any]) -> Dict[str, Any]:
        if not persona.date_of_birth:
            raise ValueError("date_of_birth is required to calculate nutrition targets")
        if persona.height_cm is None:
            raise ValueError("height_cm is required to calculate nutrition targets")
        if persona.weight_kg is None:
            raise ValueError("weight_kg is required to calculate nutrition targets")

        age = cls._calculate_age(persona.date_of_birth)
        if age <= 0:
            raise ValueError("date_of_birth is invalid for nutrition target calculation")

        weight_kg = cls._to_float(persona.weight_kg)
        height_cm = cls._to_float(persona.height_cm)
        gender = (persona.gender or "").lower()
        activity_level = (persona.activity_level or "sedentary").lower()
        activity_multiplier = cls.ACTIVITY_MULTIPLIERS.get(activity_level, cls.ACTIVITY_MULTIPLIERS["sedentary"])

        # Mifflin-St Jeor BMR.
        if gender == "male":
            gender_constant = 5
        elif gender == "female":
            gender_constant = -161
        else:
            gender_constant = -78
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + gender_constant
        tdee = bmr * activity_multiplier
        calories_kcal = max(1200, int(round(tdee)))

        kidney_stage = cls._extract_kidney_stage(conditions.get("kidney_disease_stage"))
        protein_per_kg = 1.2
        if kidney_stage is not None:
            if kidney_stage >= 4:
                protein_per_kg = 0.6
            elif kidney_stage >= 3:
                protein_per_kg = 0.8
            else:
                protein_per_kg = 1.0
        protein_g = weight_kg * protein_per_kg

        default_fat_g = (calories_kcal * 0.30) / 9
        carbs_from_remaining = (calories_kcal - (protein_g * 4) - (default_fat_g * 9)) / 4

        diabetes_status = (conditions.get("diabetes_status") or "unknown").lower()
        carb_cap_g = (calories_kcal * 0.45) / 4 if diabetes_status == "yes" else None
        carbohydrates_g = max(0.0, carbs_from_remaining)
        if carb_cap_g is not None:
            carbohydrates_g = min(carbohydrates_g, carb_cap_g)

        fat_g = max(0.0, (calories_kcal - (protein_g * 4) - (carbohydrates_g * 4)) / 9)
        fiber_g = max(25.0, (calories_kcal / 1000.0) * 14.0)

        basis = {
            "formula": "mifflin_st_jeor",
            "age_years": age,
            "gender": persona.gender or "unspecified",
            "weight_kg": round(weight_kg, 2),
            "height_cm": round(height_cm, 2),
            "activity_level": activity_level,
            "activity_multiplier": activity_multiplier,
            "bmr": round(bmr, 2),
            "tdee": round(tdee, 2),
            "diabetes_status": conditions.get("diabetes_status"),
            "hypertension_status": conditions.get("hypertension_status"),
            "kidney_disease_stage": conditions.get("kidney_disease_stage"),
            "protein_per_kg": protein_per_kg,
            "carb_cap_g": round(carb_cap_g, 2) if carb_cap_g is not None else None,
            "sodium_watch": (conditions.get("hypertension_status") or "").lower() == "yes",
        }

        return {
            "calories_kcal": calories_kcal,
            "protein_g": cls._round_metric(protein_g),
            "carbohydrates_g": cls._round_metric(carbohydrates_g),
            "fat_g": cls._round_metric(fat_g),
            "fiber_g": cls._round_metric(fiber_g),
            "calculation_basis": basis,
        }

    @classmethod
    async def _deactivate_active_targets(cls, db: AsyncSession, user_id: Any) -> None:
        await db.execute(
            update(NutritionTarget)
            .where(
                NutritionTarget.user_id == user_id,
                NutritionTarget.is_active.is_(True),
            )
            .values(is_active=False)
        )

    @classmethod
    async def upsert_calculated_target(
        cls,
        db: AsyncSession,
        user_id: Any,
        *,
        source: str = "calculated",
        target_date: Optional[date] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        persona_result = await db.execute(select(PatientPersona).where(PatientPersona.user_id == user_id))
        persona = persona_result.scalar_one_or_none()
        if not persona:
            raise ValueError("Patient persona not found")

        conditions = await cls._get_condition_context(db, user_id)
        targets = cls._calculate_target_values(persona, conditions)

        await cls._deactivate_active_targets(db, user_id)

        row = NutritionTarget(
            user_id=user_id,
            target_date=target_date or date.today(),
            source=source,
            calories_kcal=targets["calories_kcal"],
            protein_g=targets["protein_g"],
            carbohydrates_g=targets["carbohydrates_g"],
            fat_g=targets["fat_g"],
            fiber_g=targets["fiber_g"],
            calculation_basis=targets["calculation_basis"],
            is_active=True,
        )
        db.add(row)
        await db.flush()

        if commit:
            await db.commit()
        await db.refresh(row)
        return cls._serialize_target(row)

    @classmethod
    async def set_manual_target(
        cls,
        db: AsyncSession,
        user_id: Any,
        *,
        target_date: date,
        calories_kcal: int,
        protein_g: float,
        carbohydrates_g: float,
        fat_g: float,
        fiber_g: float,
        calculation_basis: Optional[Dict[str, Any]] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        await cls._deactivate_active_targets(db, user_id)
        row = NutritionTarget(
            user_id=user_id,
            target_date=target_date,
            calories_kcal=int(calories_kcal),
            protein_g=cls._round_metric(float(protein_g)),
            carbohydrates_g=cls._round_metric(float(carbohydrates_g)),
            fat_g=cls._round_metric(float(fat_g)),
            fiber_g=cls._round_metric(float(fiber_g)),
            source=source,
            calculation_basis=calculation_basis or {"manual_override": True},
            is_active=True,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return cls._serialize_target(row)

    @classmethod
    async def get_current_target(
        cls,
        db: AsyncSession,
        user_id: Any,
        *,
        target_date: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        as_of_date = target_date or date.today()
        result = await db.execute(
            select(NutritionTarget)
            .where(
                NutritionTarget.user_id == user_id,
                NutritionTarget.is_active.is_(True),
                NutritionTarget.target_date <= as_of_date,
            )
            .order_by(NutritionTarget.target_date.desc(), NutritionTarget.created_at.desc())
            .limit(1)
        )
        row = result.scalars().first()
        if not row:
            fallback = await db.execute(
                select(NutritionTarget)
                .where(
                    NutritionTarget.user_id == user_id,
                    NutritionTarget.target_date <= as_of_date,
                )
                .order_by(
                    NutritionTarget.is_active.desc(),
                    NutritionTarget.target_date.desc(),
                    NutritionTarget.created_at.desc(),
                )
                .limit(1)
            )
            row = fallback.scalars().first()
        return cls._serialize_target(row) if row else None

    @staticmethod
    def _percentage(consumed: float, target: float) -> Optional[float]:
        if target <= 0:
            return None
        return round((consumed / target) * 100, 2)

    @staticmethod
    def _adherence_status(percent: Optional[float]) -> str:
        if percent is None:
            return "n/a"
        if percent < 90:
            return "under"
        if percent <= 110:
            return "on_track"
        return "over"

    @classmethod
    async def get_adherence_for_date(
        cls,
        db: AsyncSession,
        user_id: Any,
        target_date: date,
    ) -> Dict[str, Any]:
        target = await cls.get_current_target(db, user_id, target_date=target_date)
        if not target:
            raise ValueError("No nutrition target found for requested date")

        totals_result = await db.execute(
            select(
                func.coalesce(func.sum(MealEvent.total_calories), 0),
                func.coalesce(func.sum(MealEvent.total_protein_g), 0),
                func.coalesce(func.sum(MealEvent.total_carbohydrates_g), 0),
                func.coalesce(func.sum(MealEvent.total_fat_g), 0),
                func.coalesce(func.sum(MealEvent.total_fiber_g), 0),
            ).where(
                MealEvent.user_id == user_id,
                MealEvent.meal_date == target_date,
            )
        )
        total_calories, total_protein, total_carbs, total_fat, total_fiber = totals_result.one()

        intake = {
            "calories_kcal": int(total_calories or 0),
            "protein_g": cls._round_metric(cls._to_float(total_protein)),
            "carbohydrates_g": cls._round_metric(cls._to_float(total_carbs)),
            "fat_g": cls._round_metric(cls._to_float(total_fat)),
            "fiber_g": cls._round_metric(cls._to_float(total_fiber)),
        }

        adherence: Dict[str, Dict[str, Any]] = {}
        for metric in ("calories_kcal", "protein_g", "carbohydrates_g", "fat_g", "fiber_g"):
            percent = cls._percentage(float(intake[metric]), float(target[metric]))
            adherence[metric] = {
                "percent": percent,
                "status": cls._adherence_status(percent),
            }

        return {
            "date": target_date.isoformat(),
            "target": target,
            "intake": intake,
            "adherence": adherence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
