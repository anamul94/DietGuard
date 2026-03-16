"""
Services for structured health timeline persistence and summaries.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from ...infrastructure.graphs.health_correlation_graph import summarize_health_period
from ...infrastructure.utils.nutrition_utils import metric_value as _metric_value
from .report_comparison_service import ReportComparisonService
from .health_utils import (
    build_health_context_summary,
    build_structured_report,
    grams as _grams,
    group_food_items_for_review,
    infer_condition_category,
    infer_entity_report_category,
    infer_lab_result_category,
    infer_medication_category,
    infer_report_category,
    normalize_dynamic_report,
    parse_report_date,
    parse_vitals_csv,
)

class HealthTimelineService:
    @staticmethod
    def _metric_response(value: Any, unit: str) -> Dict[str, Any]:
        return {
            "value": round(float(value or 0), 2),
            "unit": unit,
        }

    @staticmethod
    def _nutrition_totals_from_meals(meals: List[MealEvent]) -> Dict[str, Any]:
        return {
            "calories": HealthTimelineService._metric_response(sum(meal.total_calories or 0 for meal in meals), "kcal"),
            "protein": HealthTimelineService._metric_response(sum(meal.total_protein_g or 0 for meal in meals), "g"),
            "carbohydrates": HealthTimelineService._metric_response(sum(meal.total_carbohydrates_g or 0 for meal in meals), "g"),
            "fat": HealthTimelineService._metric_response(sum(meal.total_fat_g or 0 for meal in meals), "g"),
            "fiber": HealthTimelineService._metric_response(sum(meal.total_fiber_g or 0 for meal in meals), "g"),
            "sugar": HealthTimelineService._metric_response(sum(meal.total_sugar_g or 0 for meal in meals), "g"),
        }

    @staticmethod
    def _serialize_meal_items(items: List[MealItem]) -> List[Dict[str, Any]]:
        return [
            {
                "name": item.name,
                "quantity": item.quantity,
                "role": item.role,
                "preparation": item.preparation,
                "source_label": item.source_label,
                "confidence": float(item.confidence) if item.confidence is not None else None,
            }
            for item in sorted(items, key=lambda entry: entry.created_at or datetime.min.replace(tzinfo=timezone.utc))
        ]

    @staticmethod
    def _build_food_analysis_fallback(meal: MealEvent, items_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "fooditem_details": [
                {
                    "name": item["name"],
                    "quantity": item.get("quantity"),
                    "preparation": item.get("preparation"),
                    "role": item.get("role"),
                    "source_label": item.get("source_label"),
                    "confidence": item.get("confidence"),
                }
                for item in items_payload
            ],
            "nutrition": {
                "calories": HealthTimelineService._metric_response(meal.total_calories or 0, "kcal"),
                "protein": HealthTimelineService._metric_response(meal.total_protein_g or 0, "g"),
                "carbohydrates": HealthTimelineService._metric_response(meal.total_carbohydrates_g or 0, "g"),
                "fat": HealthTimelineService._metric_response(meal.total_fat_g or 0, "g"),
                "fiber": HealthTimelineService._metric_response(meal.total_fiber_g or 0, "g"),
                "sugar": HealthTimelineService._metric_response(meal.total_sugar_g or 0, "g"),
            },
        }

    @staticmethod
    def _snapshot_categories(structured_report: Dict[str, Any], default_category: str) -> List[str]:
        categories = set()
        snapshot = structured_report.get("snapshot", {})

        for condition_name, status_key in (
            ("diabetes", "diabetes_status"),
            ("hypertension", "hypertension_status"),
            ("dyslipidemia", "dyslipidemia_status"),
        ):
            if snapshot.get(status_key) == "yes":
                category = infer_condition_category(condition_name)
                if category:
                    categories.add(category)

        if snapshot.get("kidney_disease_stage"):
            categories.add("renal")

        for lab in structured_report.get("labs", []):
            category = infer_lab_result_category(lab)
            if category:
                categories.add(category)

        if not categories:
            categories.add(default_category)

        return sorted(categories)

    @staticmethod
    def _merge_current_snapshots(snapshots: List[MedicalConditionSnapshot]) -> Dict[str, Any]:
        merged = {
            "diabetes_status": "unknown",
            "hypertension_status": "unknown",
            "kidney_disease_stage": None,
            "dyslipidemia_status": "unknown",
            "food_restrictions": [],
            "allergies": [],
            "dietary_preferences": [],
            "doctor_advice": [],
            "extra_conditions": [],
        }

        ordered = sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.snapshot_date or date.min,
                snapshot.created_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        for snapshot in ordered:
            for key in ("diabetes_status", "hypertension_status", "dyslipidemia_status"):
                value = getattr(snapshot, key)
                if merged[key] == "unknown" and value != "unknown":
                    merged[key] = value
            if not merged["kidney_disease_stage"] and snapshot.kidney_disease_stage:
                merged["kidney_disease_stage"] = snapshot.kidney_disease_stage
            for key in ("food_restrictions", "allergies", "dietary_preferences", "doctor_advice", "extra_conditions"):
                merged[key] = sorted(set(merged[key]) | set(getattr(snapshot, key) or []))

        return merged

    @staticmethod
    def _serialize_report_metadata(report: MedicalReport) -> Dict[str, Any]:
        raw_payload = report.raw_payload or {}
        return {
            "report_id": str(report.id),
            "version": report.version,
            "report_date": report.report_date.isoformat() if report.report_date else None,
            "summary": report.structured_summary,
            "filenames": report.filenames or [],
            "report_category": report.report_category,
            "document_type": raw_payload.get("documentType"),
            "title": raw_payload.get("title"),
            "parser_version": report.parser_version,
            "source_documents": raw_payload.get("sourceDocuments", []) or [],
        }

    @staticmethod
    async def sync_structured_report_data(
        db: AsyncSession,
        user_id: Any,
        parsed_report: Dict[str, Any],
        filenames: List[str],
    ) -> Dict[str, Any]:
        normalized_report = normalize_dynamic_report(parsed_report)
        structured = build_structured_report(normalized_report)
        category_meta = infer_report_category(normalized_report, structured)
        primary_category = category_meta["primary_category"]
        snapshot_categories = HealthTimelineService._snapshot_categories(structured, primary_category)
        lab_categories = sorted(
            {
                infer_lab_result_category(lab) or primary_category
                for lab in structured["labs"]
            }
        ) or [primary_category]
        medication_categories = sorted(
            {
                infer_medication_category(medication, fallback_category=primary_category)
                for medication in structured["medications"]
            }
        ) or [primary_category]
        entity_categories = sorted(
            {
                infer_entity_report_category(entity, fallback_category=primary_category)
                for entity in structured["entities"] + structured["unmapped_entities"]
            }
        ) or [primary_category]

        version_result = await db.execute(
            select(func.max(MedicalReport.version)).where(MedicalReport.user_id == user_id)
        )
        current_version = version_result.scalar() or 0

        await db.execute(
            update(MedicalReport)
            .where(
                MedicalReport.user_id == user_id,
                MedicalReport.report_category == primary_category,
                MedicalReport.is_current.is_(True),
            )
            .values(is_current=False)
        )
        if snapshot_categories:
            await db.execute(
                update(MedicalConditionSnapshot)
                .where(
                    MedicalConditionSnapshot.user_id == user_id,
                    MedicalConditionSnapshot.report_category.in_(snapshot_categories),
                    MedicalConditionSnapshot.is_current.is_(True),
                )
                .values(is_current=False)
            )
        if lab_categories:
            await db.execute(
                update(LabResult)
                .where(
                    LabResult.user_id == user_id,
                    LabResult.report_category.in_(lab_categories),
                    LabResult.is_current.is_(True),
                )
                .values(is_current=False)
            )
        if medication_categories:
            await db.execute(
                update(MedicationSchedule)
                .where(
                    MedicationSchedule.user_id == user_id,
                    MedicationSchedule.report_category.in_(medication_categories),
                    MedicationSchedule.is_current.is_(True),
                )
                .values(is_current=False)
            )
        if entity_categories:
            await db.execute(
                update(MedicalReportEntity)
                .where(
                    MedicalReportEntity.user_id == user_id,
                    MedicalReportEntity.report_category.in_(entity_categories),
                    MedicalReportEntity.is_current.is_(True),
                )
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
            report_category=primary_category,
            is_current=True,
        )
        db.add(report)
        await db.flush()

        for snapshot_category in snapshot_categories:
            db.add(
                MedicalConditionSnapshot(
                    user_id=user_id,
                    source_report_id=report.id,
                    report_category=snapshot_category,
                    snapshot_date=structured["report_date"],
                    is_current=True,
                    **structured["snapshot"],
                )
            )

        for lab in structured["labs"]:
            db.add(
                LabResult(
                    user_id=user_id,
                    source_report_id=report.id,
                    report_category=infer_lab_result_category(lab) or primary_category,
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
                    report_category=infer_medication_category(medication, fallback_category=primary_category),
                    is_current=True,
                    **medication,
                )
            )

        for entity in structured["entities"] + structured["unmapped_entities"]:
            db.add(
                MedicalReportEntity(
                    user_id=user_id,
                    source_report_id=report.id,
                    report_category=infer_entity_report_category(entity, fallback_category=primary_category),
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
        
        worsening_info = await ReportComparisonService.evaluate_worsening(db, user_id)
        plan_regeneration_triggered = False
        try:
            from .diet_plan_service import DietPlanService
            from ...infrastructure.database.health_models import DietPlan
            has_active_plan = await db.scalar(
                select(DietPlan.id)
                .where(DietPlan.user_id == user_id, DietPlan.is_active.is_(True))
                .limit(1)
            )
            if not has_active_plan:
                await DietPlanService.generate_diet_plan(db, user_id, trigger="initial")
                plan_regeneration_triggered = True
            elif worsening_info.get("worsening_detected"):
                await DietPlanService.generate_diet_plan(db, user_id, trigger="worsening_detected")
                plan_regeneration_triggered = True
        except Exception:
            pass

        return {
            "report_id": str(report.id),
            "version": report.version,
            "summary": summary_text,
            "document_type": normalized_report.get("documentType"),
            "report_category": primary_category,
            "category_scopes": category_meta["category_scopes"],
            "structured": structured,
            "worsening_detected": worsening_info.get("worsening_detected", False),
            "worsening_labs": worsening_info.get("worsening_labs", []),
            "plan_regeneration_triggered": plan_regeneration_triggered,
        }

    @staticmethod
    async def get_current_health_profile(db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        report_result = await db.execute(
            select(MedicalReport)
            .where(MedicalReport.user_id == user_id)
            .order_by(MedicalReport.version.desc())
        )
        report = report_result.scalars().first()
        current_reports_result = await db.execute(
            select(MedicalReport)
            .where(MedicalReport.user_id == user_id, MedicalReport.is_current.is_(True))
            .order_by(MedicalReport.report_category.asc(), MedicalReport.report_date.desc().nulls_last(), MedicalReport.version.desc())
        )
        current_reports = current_reports_result.scalars().all()

        snapshot_result = await db.execute(
            select(MedicalConditionSnapshot).where(
                MedicalConditionSnapshot.user_id == user_id,
                MedicalConditionSnapshot.is_current.is_(True),
            )
        )
        snapshots = snapshot_result.scalars().all()

        labs_result = await db.execute(
            select(LabResult)
            .where(LabResult.user_id == user_id, LabResult.is_current.is_(True))
            .order_by(
                LabResult.report_category.asc(),
                LabResult.canonical_name.asc().nulls_last(),
                LabResult.created_at.desc(),
            )
        )
        labs = labs_result.scalars().all()

        medications_result = await db.execute(
            select(MedicationSchedule)
            .where(MedicationSchedule.user_id == user_id, MedicationSchedule.is_current.is_(True))
            .order_by(MedicationSchedule.report_category.asc(), MedicationSchedule.medication_name.asc())
        )
        medications = medications_result.scalars().all()

        entities_result = await db.execute(
            select(MedicalReportEntity)
            .where(MedicalReportEntity.user_id == user_id, MedicalReportEntity.is_current.is_(True))
            .order_by(
                MedicalReportEntity.report_category.asc(),
                MedicalReportEntity.effective_date.asc().nulls_last(),
                MedicalReportEntity.entity_type.asc(),
                MedicalReportEntity.label.asc(),
            )
        )
        entities = entities_result.scalars().all()

        trend_result: List[Dict[str, Any]] = []
        seen_trend_keys = set()
        for lab in labs:
            key = (lab.report_category, lab.canonical_name or lab.test_name)
            if key in seen_trend_keys or lab.value_numeric is None:
                continue
            seen_trend_keys.add(key)

            previous_lab_result = await db.execute(
                select(LabResult)
                .where(
                    LabResult.user_id == user_id,
                    LabResult.report_category == lab.report_category,
                    (LabResult.canonical_name == lab.canonical_name if lab.canonical_name else LabResult.test_name == lab.test_name),
                    LabResult.source_report_id != lab.source_report_id,
                )
                .order_by(LabResult.lab_date.desc().nulls_last(), LabResult.created_at.desc())
                .limit(1)
            )
            old_lab = previous_lab_result.scalars().first()
            if old_lab and old_lab.value_numeric is not None:
                trend_result.append(
                    {
                        "label": lab.canonical_name or lab.test_name,
                        "report_category": lab.report_category,
                        "current_value": float(lab.value_numeric),
                        "previous_value": float(old_lab.value_numeric),
                        "delta": float(lab.value_numeric - old_lab.value_numeric),
                        "unit": lab.unit,
                        "current_date": lab.lab_date.isoformat() if lab.lab_date else None,
                        "previous_date": old_lab.lab_date.isoformat() if old_lab.lab_date else None,
                        "trend_direction": ReportComparisonService.classify_trend(
                            float(lab.value_numeric),
                            float(old_lab.value_numeric),
                            lab.canonical_name or lab.test_name
                        )
                    }
                )

        snapshot_dict = HealthTimelineService._merge_current_snapshots(snapshots)
        lab_dicts = [
            {
                "report_category": lab.report_category,
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
                "report_category": med.report_category,
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
                "report_category": entity.report_category,
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
        active_categories = sorted(
            {
                *(snapshot.report_category for snapshot in snapshots),
                *(lab.report_category for lab in labs),
                *(med.report_category for med in medications),
                *(entity.report_category for entity in entities),
            }
        )

        return {
            "report": {
                **(HealthTimelineService._serialize_report_metadata(report) if report else {
                    "report_id": None,
                    "version": None,
                    "report_date": None,
                    "summary": None,
                    "filenames": [],
                    "report_category": None,
                    "document_type": None,
                    "title": None,
                    "parser_version": None,
                    "source_documents": [],
                }),
            },
            "current_reports": [HealthTimelineService._serialize_report_metadata(current_report) for current_report in current_reports],
            "snapshot": snapshot_dict,
            "labs": lab_dicts,
            "medications": medication_dicts,
            "entities": entity_dicts,
            "sections": sections,
            "unmapped_entities": unmapped_entities,
            "lab_trends": trend_result,
            "active_categories": active_categories,
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
        source: str = "image",
    ) -> MealEvent:
        meal_datetime = datetime.combine(meal_date, meal_time_value, tzinfo=timezone.utc)
        meal_event = MealEvent(
            user_id=user_id,
            meal_type=meal_type,
            meal_date=meal_date,
            meal_time=meal_datetime,
            source=source,
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
    async def get_todays_meal_nutrition_summary(
        db: AsyncSession,
        user_id: Any,
        target_date: date,
    ) -> Dict[str, Any]:
        meals_result = await db.execute(
            select(MealEvent)
            .where(MealEvent.user_id == user_id, MealEvent.meal_date == target_date)
            .order_by(MealEvent.meal_time.asc())
        )
        meals = meals_result.scalars().all()

        return {
            "date": target_date.isoformat(),
            "meal_count": len(meals),
            "nutrition_totals": HealthTimelineService._nutrition_totals_from_meals(meals),
        }

    @staticmethod
    async def get_meal_history(
        db: AsyncSession,
        user_id: Any,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        filters = [MealEvent.user_id == user_id]
        if start_date:
            filters.append(MealEvent.meal_date >= start_date)
        if end_date:
            filters.append(MealEvent.meal_date <= end_date)

        total_count_result = await db.execute(
            select(func.count())
            .select_from(MealEvent)
            .where(*filters)
        )
        total_count = total_count_result.scalar() or 0
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        offset = (page - 1) * page_size

        meals_result = await db.execute(
            select(MealEvent)
            .options(selectinload(MealEvent.items), selectinload(MealEvent.media))
            .where(*filters)
            .order_by(MealEvent.meal_date.desc(), MealEvent.meal_time.desc(), MealEvent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        meals = meals_result.scalars().all()

        history_items = []
        for meal in meals:
            serialized_items = HealthTimelineService._serialize_meal_items(list(meal.items or []))
            food_analysis = HealthTimelineService._build_food_analysis_fallback(meal, serialized_items)

            history_items.append(
                {
                    "meal_event_id": str(meal.id),
                    "meal_type": meal.meal_type,
                    "meal_date": meal.meal_date.isoformat(),
                    "meal_time": meal.meal_time.isoformat(),
                    "source": meal.source,
                    "notes": meal.notes,
                    "food_names": [item["name"] for item in serialized_items],
                    "items": serialized_items,
                    "source_filenames": [media.filename for media in sorted(meal.media or [], key=lambda entry: entry.created_at or datetime.min.replace(tzinfo=timezone.utc))],
                    "nutrition_totals": {
                        "calories": HealthTimelineService._metric_response(meal.total_calories or 0, "kcal"),
                        "protein": HealthTimelineService._metric_response(meal.total_protein_g or 0, "g"),
                        "carbohydrates": HealthTimelineService._metric_response(meal.total_carbohydrates_g or 0, "g"),
                        "fat": HealthTimelineService._metric_response(meal.total_fat_g or 0, "g"),
                        "fiber": HealthTimelineService._metric_response(meal.total_fiber_g or 0, "g"),
                        "sugar": HealthTimelineService._metric_response(meal.total_sugar_g or 0, "g"),
                    },
                    "food_analysis": food_analysis,
                }
            )

        return {
            "items": history_items,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @staticmethod
    async def delete_report_history(
        db: AsyncSession,
        user_id: Any,
    ) -> int:
        count_result = await db.execute(
            select(func.count())
            .select_from(MedicalReport)
            .where(MedicalReport.user_id == user_id)
        )
        total_reports = count_result.scalar() or 0
        if total_reports == 0:
            return 0

        await db.execute(delete(MedicalReport).where(MedicalReport.user_id == user_id))
        await db.commit()
        return total_reports

    @staticmethod
    async def create_mood_checkin(
        *,
        db: AsyncSession,
        user_id: Any,
        audio_filename: Optional[str],
        transcript: str,
        mood_label: Optional[str],
        stress_level_1_5: Optional[int],
        symptom_flags: Dict[str, Any],
        captured_at: datetime,
        source: str = "audio",
    ) -> MoodCheckIn:
        checkin = MoodCheckIn(
            user_id=user_id,
            source=source,
            audio_filename=audio_filename,
            transcript=transcript,
            mood_label=mood_label,
            stress_level=stress_level_1_5,
            symptom_flags=symptom_flags or {},
            captured_at=captured_at,
        )
        db.add(checkin)
        await db.commit()
        await db.refresh(checkin)
        return checkin

    @staticmethod
    async def get_mood_history(
        *,
        db: AsyncSession,
        user_id: Any,
        start_date: Optional[date],
        end_date: Optional[date],
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        # Date filtering is inclusive, using UTC day boundaries.
        start_dt = (
            datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
            if start_date
            else datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
        end_dt = (
            datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
            if end_date
            else datetime(2100, 1, 1, tzinfo=timezone.utc)
        )

        count_result = await db.execute(
            select(func.count())
            .select_from(MoodCheckIn)
            .where(MoodCheckIn.user_id == user_id, MoodCheckIn.captured_at >= start_dt, MoodCheckIn.captured_at <= end_dt)
        )
        total_count = int(count_result.scalar() or 0)

        offset = (page - 1) * page_size
        result = await db.execute(
            select(MoodCheckIn)
            .where(MoodCheckIn.user_id == user_id, MoodCheckIn.captured_at >= start_dt, MoodCheckIn.captured_at <= end_dt)
            .order_by(MoodCheckIn.captured_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = result.scalars().all()
        total_pages = (total_count + page_size - 1) // page_size if page_size else 0

        return {
            "items": rows,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

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
