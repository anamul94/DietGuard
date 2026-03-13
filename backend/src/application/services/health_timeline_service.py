"""
Services for structured health timeline persistence and summaries.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.database.health_models import (
    LabResult,
    MealEvent,
    MealItem,
    MealMedia,
    MedicalConditionSnapshot,
    MedicalReport,
    MedicalReportEntity,
    MedicationSchedule,
    MoodCheckIn,
    VitalEvent,
)
from ...infrastructure.database.models import NutritionData
from ...infrastructure.graphs.health_correlation_graph import summarize_health_period
from ...infrastructure.utils.nutrition_utils import metric_value as _metric_value
from .health_utils import (
    build_health_context_summary,
    build_structured_report,
    grams as _grams,
    group_food_items_for_review,
    normalize_dynamic_report,
    parse_report_date,
    parse_vitals_csv,
)


class HealthTimelineService:
    @staticmethod
    async def sync_structured_report_data(
        db: AsyncSession,
        user_id: Any,
        parsed_report: Dict[str, Any],
        filenames: List[str],
    ) -> Dict[str, Any]:
        normalized_report = normalize_dynamic_report(parsed_report)
        structured = build_structured_report(normalized_report)

        version_result = await db.execute(
            select(func.max(MedicalReport.version)).where(MedicalReport.user_id == user_id)
        )
        current_version = version_result.scalar() or 0

        await db.execute(
            update(MedicalReport).where(MedicalReport.user_id == user_id, MedicalReport.is_current.is_(True)).values(is_current=False)
        )
        await db.execute(
            update(MedicalConditionSnapshot)
            .where(MedicalConditionSnapshot.user_id == user_id, MedicalConditionSnapshot.is_current.is_(True))
            .values(is_current=False)
        )
        await db.execute(
            update(LabResult).where(LabResult.user_id == user_id, LabResult.is_current.is_(True)).values(is_current=False)
        )
        await db.execute(
            update(MedicationSchedule)
            .where(MedicationSchedule.user_id == user_id, MedicationSchedule.is_current.is_(True))
            .values(is_current=False)
        )
        await db.execute(
            update(MedicalReportEntity)
            .where(MedicalReportEntity.user_id == user_id, MedicalReportEntity.is_current.is_(True))
            .values(is_current=False)
        )

        summary_text = build_health_context_summary(structured["snapshot"], structured["labs"], structured["medications"])
        report = MedicalReport(
            user_id=user_id,
            version=current_version + 1,
            filenames=filenames,
            raw_payload=normalized_report,
            structured_summary=summary_text,
            report_date=structured["report_date"],
            parser_version="report_agent_v3_dynamic",
            is_current=True,
        )
        db.add(report)
        await db.flush()

        snapshot = MedicalConditionSnapshot(
            user_id=user_id,
            source_report_id=report.id,
            snapshot_date=structured["report_date"],
            is_current=True,
            **structured["snapshot"],
        )
        db.add(snapshot)

        for lab in structured["labs"]:
            db.add(
                LabResult(
                    user_id=user_id,
                    source_report_id=report.id,
                    is_current=True,
                    lab_date=structured["report_date"],
                    **lab,
                )
            )

        for medication in structured["medications"]:
            db.add(
                MedicationSchedule(
                    user_id=user_id,
                    source_report_id=report.id,
                    is_current=True,
                    **medication,
                )
            )

        for entity in structured["entities"] + structured["unmapped_entities"]:
            db.add(
                MedicalReportEntity(
                    user_id=user_id,
                    source_report_id=report.id,
                    is_current=True,
                    entity_type=entity.get("entity_type") or "other",
                    category=entity.get("category"),
                    label=entity.get("label") or "Unknown entity",
                    canonical_name=entity.get("canonical_name"),
                    value_text=entity.get("value_text"),
                    value_numeric=entity.get("value_numeric"),
                    unit=entity.get("unit"),
                    reference_range=entity.get("reference_range"),
                    interpretation=entity.get("interpretation"),
                    status=entity.get("status"),
                    effective_date=parse_report_date(entity.get("effective_date")),
                    source_section=entity.get("source_section"),
                    source_text=entity.get("source_text"),
                    page_number=entity.get("page_number"),
                    confidence=entity.get("confidence"),
                    attributes=entity.get("attributes") or {},
                )
            )

        await db.commit()
        return {
            "report_id": str(report.id),
            "version": report.version,
            "summary": summary_text,
            "document_type": normalized_report.get("documentType"),
            "structured": structured,
        }

    @staticmethod
    async def get_current_health_profile(db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        report_result = await db.execute(
            select(MedicalReport)
            .where(MedicalReport.user_id == user_id, MedicalReport.is_current.is_(True))
            .order_by(MedicalReport.version.desc())
        )
        report = report_result.scalars().first()

        snapshot_result = await db.execute(
            select(MedicalConditionSnapshot).where(
                MedicalConditionSnapshot.user_id == user_id,
                MedicalConditionSnapshot.is_current.is_(True),
            )
        )
        snapshot = snapshot_result.scalars().first()

        labs_result = await db.execute(
            select(LabResult)
            .where(LabResult.user_id == user_id, LabResult.is_current.is_(True))
            .order_by(LabResult.canonical_name.asc().nulls_last(), LabResult.created_at.desc())
        )
        labs = labs_result.scalars().all()

        medications_result = await db.execute(
            select(MedicationSchedule)
            .where(MedicationSchedule.user_id == user_id, MedicationSchedule.is_current.is_(True))
            .order_by(MedicationSchedule.medication_name.asc())
        )
        medications = medications_result.scalars().all()

        entities_result = await db.execute(
            select(MedicalReportEntity)
            .where(MedicalReportEntity.user_id == user_id, MedicalReportEntity.is_current.is_(True))
            .order_by(
                MedicalReportEntity.effective_date.asc().nulls_last(),
                MedicalReportEntity.entity_type.asc(),
                MedicalReportEntity.label.asc(),
            )
        )
        entities = entities_result.scalars().all()

        previous_report_result = await db.execute(
            select(MedicalReport)
            .where(MedicalReport.user_id == user_id)
            .order_by(MedicalReport.version.desc())
            .offset(1)
            .limit(1)
        )
        previous_report = previous_report_result.scalars().first()

        trend_result: List[Dict[str, Any]] = []
        if report and previous_report:
            current_labs_result = await db.execute(
                select(LabResult).where(LabResult.source_report_id == report.id)
            )
            previous_labs_result = await db.execute(
                select(LabResult).where(LabResult.source_report_id == previous_report.id)
            )
            previous_labs_by_name = {
                lab.canonical_name or lab.test_name: lab for lab in previous_labs_result.scalars().all()
            }
            for lab in current_labs_result.scalars().all():
                key = lab.canonical_name or lab.test_name
                old_lab = previous_labs_by_name.get(key)
                if old_lab and lab.value_numeric is not None and old_lab.value_numeric is not None:
                    trend_result.append(
                        {
                            "label": key,
                            "current_value": float(lab.value_numeric),
                            "previous_value": float(old_lab.value_numeric),
                            "delta": float(lab.value_numeric - old_lab.value_numeric),
                            "unit": lab.unit,
                        }
                    )

        snapshot_dict = {
            "diabetes_status": snapshot.diabetes_status if snapshot else "unknown",
            "hypertension_status": snapshot.hypertension_status if snapshot else "unknown",
            "kidney_disease_stage": snapshot.kidney_disease_stage if snapshot else None,
            "dyslipidemia_status": snapshot.dyslipidemia_status if snapshot else "unknown",
            "food_restrictions": snapshot.food_restrictions if snapshot else [],
            "allergies": snapshot.allergies if snapshot else [],
            "dietary_preferences": snapshot.dietary_preferences if snapshot else [],
            "doctor_advice": snapshot.doctor_advice if snapshot else [],
            "extra_conditions": snapshot.extra_conditions if snapshot else [],
        }
        lab_dicts = [
            {
                "test_name": lab.test_name,
                "canonical_name": lab.canonical_name,
                "value_text": lab.value_text,
                "value_numeric": float(lab.value_numeric) if lab.value_numeric is not None else None,
                "unit": lab.unit,
                "reference_range": lab.reference_range,
                "interpretation": lab.interpretation,
                "abnormal_flag": lab.abnormal_flag,
                "lab_date": lab.lab_date.isoformat() if lab.lab_date else None,
            }
            for lab in labs
        ]
        medication_dicts = [
            {
                "medication_name": med.medication_name,
                "dosage": med.dosage,
                "schedule": med.schedule,
                "timing_notes": med.timing_notes,
                "with_food": med.with_food,
            }
            for med in medications
        ]
        entity_dicts = [
            {
                "entity_type": entity.entity_type,
                "category": entity.category,
                "label": entity.label,
                "canonical_name": entity.canonical_name,
                "value_text": entity.value_text,
                "value_numeric": float(entity.value_numeric) if entity.value_numeric is not None else None,
                "unit": entity.unit,
                "reference_range": entity.reference_range,
                "interpretation": entity.interpretation,
                "status": entity.status,
                "effective_date": entity.effective_date.isoformat() if entity.effective_date else None,
                "source_section": entity.source_section,
                "source_text": entity.source_text,
                "page_number": entity.page_number,
                "confidence": float(entity.confidence) if entity.confidence is not None else None,
                "attributes": entity.attributes or {},
            }
            for entity in entities
        ]
        sections = []
        unmapped_entities = []
        if report and isinstance(report.raw_payload, dict):
            sections = report.raw_payload.get("sections", []) or []
            unmapped_entities = report.raw_payload.get("unmappedEntities", []) or []

        return {
            "report": {
                "version": report.version if report else None,
                "report_date": report.report_date.isoformat() if report and report.report_date else None,
                "summary": report.structured_summary if report else None,
                "filenames": report.filenames if report else [],
                "document_type": (report.raw_payload or {}).get("documentType") if report else None,
                "title": (report.raw_payload or {}).get("title") if report else None,
                "parser_version": report.parser_version if report else None,
                "source_documents": (report.raw_payload or {}).get("sourceDocuments", []) if report else [],
            },
            "snapshot": snapshot_dict,
            "labs": lab_dicts,
            "medications": medication_dicts,
            "entities": entity_dicts,
            "sections": sections,
            "unmapped_entities": unmapped_entities,
            "lab_trends": trend_result,
            "health_context_summary": build_health_context_summary(snapshot_dict, lab_dicts, medication_dicts),
        }

    @staticmethod
    async def create_meal_event(
        db: AsyncSession,
        user_id: Any,
        meal_type: str,
        meal_date: date,
        meal_time_value: time,
        items: List[Dict[str, Any]],
        nutrition: Dict[str, Any],
        fooditem_details: Optional[List[Dict[str, Any]]] = None,
        source_filenames: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> MealEvent:
        meal_datetime = datetime.combine(meal_date, meal_time_value, tzinfo=timezone.utc)
        meal_event = MealEvent(
            user_id=user_id,
            meal_type=meal_type,
            meal_date=meal_date,
            meal_time=meal_datetime,
            total_calories=int(round(_metric_value(nutrition.get("calories"), default_unit="kcal") or 0)),
            total_protein_g=_grams(nutrition.get("protein")),
            total_carbohydrates_g=_grams(nutrition.get("carbohydrates")),
            total_fat_g=_grams(nutrition.get("fat")),
            total_fiber_g=_grams(nutrition.get("fiber")),
            total_sugar_g=_grams(nutrition.get("sugar")),
            notes=notes,
        )
        db.add(meal_event)
        await db.flush()

        for item in items:
            db.add(
                MealItem(
                    meal_event_id=meal_event.id,
                    user_id=user_id,
                    name=item["name"],
                    quantity=item.get("quantity"),
                    role=item.get("role") or "main",
                    preparation=item.get("preparation"),
                    source_label=item.get("source_label"),
                    confidence=item.get("confidence"),
                    is_user_confirmed=True,
                )
            )

        for filename in source_filenames or []:
            db.add(
                MealMedia(
                    meal_event_id=meal_event.id,
                    user_id=user_id,
                    filename=filename,
                    source="image",
                )
            )

        db.add(
            NutritionData(
                user_id=str(user_id),
                data=json.dumps(
                    {
                        "food_analysis": {
                            "fooditem_details": fooditem_details or [
                                {
                                    "name": item["name"],
                                    "quantity": item.get("quantity"),
                                    "preparation": item.get("preparation"),
                                }
                                for item in items
                            ],
                            "nutrition": nutrition,
                        },
                        "meal_type": meal_type,
                        "meal_time": meal_time_value.isoformat(timespec="minutes"),
                        "meal_date": meal_date.isoformat(),
                        "source": "confirmed_meal",
                    }
                ),
                expires_at=None,
                meal_time=meal_time_value,
                meal_date=meal_date,
            )
        )

        await db.commit()
        await db.refresh(meal_event)
        return meal_event

    @staticmethod
    async def create_vital_events(
        db: AsyncSession,
        user_id: Any,
        entries: List[Dict[str, Any]],
        source: str,
        source_device: Optional[str] = None,
    ) -> List[VitalEvent]:
        created = []
        for entry in entries:
            vital = VitalEvent(
                user_id=user_id,
                source=source,
                source_device=source_device or entry.get("source_device"),
                vital_type=entry["vital_type"],
                value_primary=entry["value_primary"],
                value_secondary=entry.get("value_secondary"),
                unit=entry["unit"],
                notes=entry.get("notes"),
                extra_metadata=entry.get("metadata") or {},
                captured_at=entry["captured_at"],
            )
            db.add(vital)
            created.append(vital)

        await db.commit()
        return created

    @staticmethod
    async def get_period_insights(
        db: AsyncSession,
        user_id: Any,
        start_datetime: datetime,
        end_datetime: datetime,
        label: str,
    ) -> Dict[str, Any]:
        meals_result = await db.execute(
            select(MealEvent)
            .where(MealEvent.user_id == user_id, MealEvent.meal_time >= start_datetime, MealEvent.meal_time <= end_datetime)
            .order_by(MealEvent.meal_time.asc())
        )
        meals = meals_result.scalars().all()

        vitals_result = await db.execute(
            select(VitalEvent)
            .where(VitalEvent.user_id == user_id, VitalEvent.captured_at >= start_datetime, VitalEvent.captured_at <= end_datetime)
            .order_by(VitalEvent.captured_at.asc())
        )
        vitals = vitals_result.scalars().all()

        mood_result = await db.execute(
            select(MoodCheckIn)
            .where(MoodCheckIn.user_id == user_id, MoodCheckIn.captured_at >= start_datetime, MoodCheckIn.captured_at <= end_datetime)
            .order_by(MoodCheckIn.captured_at.asc())
        )
        mood_checkins = mood_result.scalars().all()

        health_profile = await HealthTimelineService.get_current_health_profile(db, user_id)

        graph_output = summarize_health_period(
            meals=[
                {
                    "id": str(meal.id),
                    "meal_type": meal.meal_type,
                    "meal_date": meal.meal_date.isoformat(),
                    "meal_time": meal.meal_time.isoformat(),
                    "total_calories": meal.total_calories,
                    "total_carbohydrates_g": float(meal.total_carbohydrates_g) if meal.total_carbohydrates_g is not None else None,
                    "total_fat_g": float(meal.total_fat_g) if meal.total_fat_g is not None else None,
                }
                for meal in meals
            ],
            vitals=[
                {
                    "id": str(vital.id),
                    "vital_type": vital.vital_type,
                    "value_primary": float(vital.value_primary),
                    "value_secondary": float(vital.value_secondary) if vital.value_secondary is not None else None,
                    "unit": vital.unit,
                    "captured_at": vital.captured_at.isoformat(),
                    "source": vital.source,
                }
                for vital in vitals
            ],
            mood_checkins=[
                {
                    "id": str(checkin.id),
                    "mood_label": checkin.mood_label,
                    "stress_level": checkin.stress_level,
                    "sleep_quality": checkin.sleep_quality,
                    "captured_at": checkin.captured_at.isoformat(),
                }
                for checkin in mood_checkins
            ],
            health_profile=health_profile,
            period_label=label,
        )

        nutrition_totals = {
            "calories": sum(meal.total_calories or 0 for meal in meals),
            "protein_g": float(sum(meal.total_protein_g or 0 for meal in meals)),
            "carbohydrates_g": float(sum(meal.total_carbohydrates_g or 0 for meal in meals)),
            "fat_g": float(sum(meal.total_fat_g or 0 for meal in meals)),
        }

        vital_overview = []
        by_type: Dict[str, List[VitalEvent]] = {}
        for vital in vitals:
            by_type.setdefault(vital.vital_type, []).append(vital)
        for vital_type, entries in by_type.items():
            avg_primary = sum(float(entry.value_primary) for entry in entries) / len(entries)
            vital_overview.append(
                {
                    "vital_type": vital_type,
                    "count": len(entries),
                    "average_primary": round(avg_primary, 2),
                    "unit": entries[0].unit,
                }
            )

        return {
            "period_start": start_datetime.isoformat(),
            "period_end": end_datetime.isoformat(),
            "meal_count": len(meals),
            "vital_count": len(vitals),
            "mood_checkin_count": len(mood_checkins),
            "nutrition_totals": nutrition_totals,
            "vital_overview": vital_overview,
            "associations": graph_output["associations"],
            "narrative": graph_output["narrative"],
            "possible_factors": graph_output["possible_factors"],
        }
