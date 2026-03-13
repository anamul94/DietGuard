"""
Pure helpers for structured health normalization.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from ...infrastructure.utils.nutrition_utils import metric_value


LAB_NAME_MAPPINGS = {
    "hba1c": [r"\bhba1c\b", r"\bha1c\b", r"glycated hemoglobin"],
    "glucose": [r"fasting glucose", r"\bglucose\b", r"blood sugar", r"\bfbs\b", r"\brbs\b"],
    "ldl": [r"\bldl\b", r"ldl cholesterol", r"low density lipoprotein"],
    "hdl": [r"\bhdl\b", r"hdl cholesterol", r"high density lipoprotein"],
    "triglycerides": [r"triglycerides?"],
    "creatinine": [r"creatinine"],
    "uric_acid": [r"uric acid"],
    "total_cholesterol": [r"total cholesterol", r"\bcholesterol\b"],
    "urea": [r"\burea\b", r"blood urea"],
    "bun": [r"\bbun\b", r"blood urea nitrogen"],
    "hemoglobin": [r"\bhemoglobin\b", r"\bhb\b"],
    "platelets": [r"platelets?"],
    "wbc": [r"\bwbc\b", r"white blood cells?"],
    "rbc": [r"\brbc\b", r"red blood cells?"],
    "vitamin_d": [r"vitamin d"],
    "vitamin_b12": [r"vitamin b12", r"\bb12\b"],
    "tsh": [r"\btsh\b", r"thyroid stimulating hormone"],
}

CONDITION_PATTERNS = {
    "diabetes": [r"diabet", r"hyperglyc", r"high hba1c", r"high glucose"],
    "hypertension": [r"hypertension", r"high blood pressure"],
    "dyslipidemia": [r"dyslipid", r"hyperlipid", r"high ldl", r"high cholesterol", r"high triglycerides"],
    "kidney_disease": [r"kidney disease", r"ckd", r"renal disease", r"chronic kidney"],
}

ROLE_PATTERNS = {
    "condiment": [r"sauce", r"dressing", r"dip", r"chutney", r"spread"],
    "side": [r"salad", r"pickle", r"slaw", r"fries", r"chips", r"soup"],
    "beverage": [r"juice", r"tea", r"coffee", r"soda", r"cola", r"water", r"shake"],
}

ENTITY_TYPE_ALIASES = {
    "diagnosis": "condition",
    "problem": "condition",
    "medical_condition": "condition",
    "disease": "condition",
    "lab": "observation",
    "observation": "observation",
    "measurement": "observation",
    "test_result": "observation",
    "medicine": "medication",
    "drug": "medication",
    "prescription": "medication",
    "dietary_restriction": "restriction",
    "food_restriction": "restriction",
    "preference": "restriction",
    "advice": "recommendation",
    "recommendation": "recommendation",
    "plan": "recommendation",
    "finding": "finding",
    "impression": "finding",
    "symptom": "finding",
    "procedure": "procedure",
    "encounter": "encounter",
    "visit": "encounter",
    "allergy": "allergy",
}

DOCUMENT_TYPE_HINTS = {
    "lab_report": [r"lab", r"laboratory", r"pathology", r"biochemistry", r"hematology", r"cbc", r"lipid profile"],
    "prescription": [r"prescription", r"\brx\b", r"tablet", r"capsule", r"take once", r"take twice"],
    "discharge_summary": [r"discharge", r"hospital course", r"admission", r"discharged on"],
    "radiology_report": [r"radiology", r"\bmri\b", r"\bct\b", r"x-ray", r"ultrasound", r"impression"],
    "consultation_note": [r"consult", r"assessment", r"plan", r"follow-up", r"chief complaint"],
}

KNOWN_ENTITY_KEYS = {
    "entityType",
    "entity_type",
    "type",
    "category",
    "label",
    "testName",
    "name",
    "title",
    "condition",
    "medication",
    "valueText",
    "value_text",
    "value",
    "result",
    "valueNumeric",
    "value_numeric",
    "unit",
    "referenceRange",
    "reference_range",
    "interpretation",
    "status",
    "effectiveDate",
    "effective_date",
    "date",
    "labDate",
    "sourceSection",
    "source_section",
    "section",
    "sourceText",
    "source_text",
    "excerpt",
    "pageNumber",
    "page_number",
    "confidence",
    "attributes",
    "canonicalName",
    "canonical_name",
    "summary",
    "rawText",
    "raw_text",
}


def json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    return str(value)


def parse_llm_json_payload(value: Any) -> Optional[Dict[str, Any] | List[Any]]:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    candidates = [text]

    fenced = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced)
    if fenced != text:
        candidates.append(fenced.strip())

    first_object = text.find("{")
    last_object = text.rfind("}")
    if first_object != -1 and last_object != -1 and last_object > first_object:
        candidates.append(text[first_object:last_object + 1].strip())

    first_array = text.find("[")
    last_array = text.rfind("]")
    if first_array != -1 and last_array != -1 and last_array > first_array:
        candidates.append(text[first_array:last_array + 1].strip())

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, str) and parsed.strip() != candidate:
            nested = parse_llm_json_payload(parsed)
            if nested is not None:
                return nested
        return parsed

    return None


def coerce_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def normalize_status(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    normalized = value.strip().lower()
    if normalized in {"yes", "positive", "present", "true", "diagnosed", "detected"}:
        return "yes"
    if normalized in {"no", "negative", "absent", "false", "ruled out"}:
        return "no"
    if normalized in {"unknown", "unclear", "not stated", "n/a"}:
        return "unknown"
    return value.strip()


def extract_numeric(value: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if not value:
        return None, None
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z%/._-]+)?", value)
    if not match:
        return None, None
    numeric = float(match.group(1))
    unit = match.group(2)
    return numeric, unit


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def canonical_lab_name(test_name: Optional[str]) -> Optional[str]:
    if not test_name:
        return None
    lowered = test_name.lower()
    for canonical_name_value, patterns in LAB_NAME_MAPPINGS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            return canonical_name_value
    return None


def canonical_condition_name(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    lowered = text.lower()
    for condition_name, patterns in CONDITION_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            return condition_name
    return None


def contains_condition(text_blocks: Iterable[str], condition_name: str) -> str:
    patterns = CONDITION_PATTERNS.get(condition_name, [])
    for block in text_blocks:
        lowered = block.lower()
        if any(re.search(pattern, lowered) for pattern in patterns):
            return "yes"
    return "unknown"


def parse_report_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def grams(value: Any) -> Optional[Decimal]:
    numeric = metric_value(value, default_unit="g")
    if numeric is None:
        return None
    try:
        return Decimal(str(numeric))
    except InvalidOperation:
        return None


def normalize_entity_type(value: Optional[str]) -> str:
    if not value:
        return "other"
    normalized = re.sub(r"[^a-z0-9_ ]", "", value.strip().lower()).replace(" ", "_")
    return ENTITY_TYPE_ALIASES.get(normalized, normalized or "other")


def normalize_entity_category(value: Optional[str], entity_type: str, label: Optional[str] = None) -> Optional[str]:
    if value:
        normalized = re.sub(r"[^a-z0-9_ ]", "", value.strip().lower()).replace(" ", "_")
        return normalized or None
    if entity_type == "observation":
        if canonical_lab_name(label):
            return "lab"
        return "observation"
    if entity_type == "condition":
        return "diagnosis"
    if entity_type == "medication":
        return "prescription"
    if entity_type == "restriction":
        return "diet"
    if entity_type == "recommendation":
        return "advice"
    return None


def _build_source_text(label: Optional[str], value_text: Optional[str], reference_range: Optional[str]) -> Optional[str]:
    bits = [bit for bit in [label, value_text, reference_range] if bit]
    if not bits:
        return None
    return " | ".join(bits)


def _normalize_attributes(payload: Dict[str, Any]) -> Dict[str, Any]:
    attributes = payload.get("attributes")
    normalized = json_safe_value(attributes) if isinstance(attributes, dict) else {}
    for key, value in payload.items():
        if key in KNOWN_ENTITY_KEYS:
            continue
        normalized[str(key)] = json_safe_value(value)
    return normalized


def _infer_canonical_name(entity_type: str, label: Optional[str], value_text: Optional[str]) -> Optional[str]:
    if entity_type == "observation":
        return canonical_lab_name(label or value_text)
    if entity_type == "condition":
        return canonical_condition_name(" ".join(bit for bit in [label, value_text] if bit))
    return None


def normalize_entity(
    entity: Any,
    *,
    default_entity_type: str = "other",
    default_category: Optional[str] = None,
    default_section: Optional[str] = None,
    default_date: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    if entity is None:
        return None

    if not isinstance(entity, dict):
        text = coerce_string(entity)
        if not text:
            return None
        return {
            "entity_type": normalize_entity_type(default_entity_type),
            "category": default_category,
            "label": text,
            "canonical_name": _infer_canonical_name(normalize_entity_type(default_entity_type), text, text),
            "value_text": text,
            "value_numeric": None,
            "unit": None,
            "reference_range": None,
            "interpretation": None,
            "status": None,
            "effective_date": default_date.isoformat() if default_date else None,
            "source_section": default_section,
            "source_text": text,
            "page_number": None,
            "confidence": None,
            "attributes": {},
        }

    entity_type = normalize_entity_type(
        coerce_string(entity.get("entityType") or entity.get("entity_type") or entity.get("type")) or default_entity_type
    )
    label = coerce_string(
        entity.get("label")
        or entity.get("testName")
        or entity.get("name")
        or entity.get("title")
        or entity.get("condition")
        or entity.get("medication")
    )
    value_text = coerce_string(
        entity.get("valueText")
        or entity.get("value_text")
        or entity.get("value")
        or entity.get("result")
    )
    value_numeric = _coerce_float(entity.get("valueNumeric") or entity.get("value_numeric"))
    unit = coerce_string(entity.get("unit"))
    if value_numeric is None and value_text:
        value_numeric, inferred_unit = extract_numeric(value_text)
        if not unit:
            unit = inferred_unit

    reference_range = coerce_string(entity.get("referenceRange") or entity.get("reference_range"))
    interpretation = coerce_string(entity.get("interpretation"))
    status = coerce_string(entity.get("status"))
    effective_date = parse_report_date(
        coerce_string(entity.get("effectiveDate") or entity.get("effective_date") or entity.get("date") or entity.get("labDate"))
    ) or default_date
    source_section = coerce_string(
        entity.get("sourceSection") or entity.get("source_section") or entity.get("section")
    ) or default_section
    source_text = coerce_string(
        entity.get("sourceText") or entity.get("source_text") or entity.get("excerpt") or entity.get("rawText") or entity.get("raw_text")
    )
    page_number = _coerce_int(entity.get("pageNumber") or entity.get("page_number"))
    confidence = _coerce_float(entity.get("confidence"))
    attributes = _normalize_attributes(entity)

    category = normalize_entity_category(
        coerce_string(entity.get("category")), entity_type, label or value_text
    ) or default_category
    canonical_name = coerce_string(entity.get("canonicalName") or entity.get("canonical_name")) or _infer_canonical_name(
        entity_type, label, value_text
    )

    if not label:
        if canonical_name:
            label = canonical_name.replace("_", " ").title()
        elif value_text:
            label = value_text
        else:
            label = f"{entity_type.replace('_', ' ').title()} item"

    if not source_text:
        source_text = _build_source_text(label, value_text, reference_range)

    return {
        "entity_type": entity_type,
        "category": category,
        "label": label,
        "canonical_name": canonical_name,
        "value_text": value_text,
        "value_numeric": value_numeric,
        "unit": unit,
        "reference_range": reference_range,
        "interpretation": interpretation,
        "status": status,
        "effective_date": effective_date.isoformat() if effective_date else None,
        "source_section": source_section,
        "source_text": source_text,
        "page_number": page_number,
        "confidence": confidence,
        "attributes": attributes,
    }


def normalize_section(section: Any, *, fallback_name: str, fallback_kind: str = "other") -> Optional[Dict[str, Any]]:
    if section is None:
        return None
    if not isinstance(section, dict):
        text = coerce_string(section)
        if not text:
            return None
        return {
            "name": fallback_name,
            "kind": fallback_kind,
            "summary": text,
            "page_number": None,
            "attributes": {},
        }

    name = coerce_string(section.get("name") or section.get("title")) or fallback_name
    kind = coerce_string(section.get("kind") or section.get("type")) or fallback_kind
    summary = coerce_string(section.get("summary") or section.get("content") or section.get("text") or section.get("rawText"))
    page_number = _coerce_int(section.get("pageNumber") or section.get("page_number"))
    attributes = {
        key: json_safe_value(value)
        for key, value in section.items()
        if key not in {"name", "title", "kind", "type", "summary", "content", "text", "rawText", "pageNumber", "page_number"}
    }
    return {
        "name": name,
        "kind": kind,
        "summary": summary,
        "page_number": page_number,
        "attributes": attributes,
    }


def extract_legacy_entities(parsed_report: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    report_date = parse_report_date(
        coerce_string(parsed_report.get("reportDate") or parsed_report.get("report_date") or parsed_report.get("effectiveDateTime"))
    )
    entities: List[Dict[str, Any]] = []
    sections: List[Dict[str, Any]] = []

    results = parsed_report.get("result", []) or []
    if results:
        sections.append({"name": "Results", "kind": "results", "summary": None, "page_number": None, "attributes": {}})
    for result in results:
        normalized = normalize_entity(
            result,
            default_entity_type="observation",
            default_category="lab",
            default_section="Results",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)

    conditions = parsed_report.get("conditions", {}) or {}
    explicit_conditions = {
        "diabetes": conditions.get("diabetes"),
        "hypertension": conditions.get("hypertension"),
        "dyslipidemia": conditions.get("dyslipidemia"),
        "kidney disease": conditions.get("kidneyDiseaseStage"),
    }
    if any(value for value in explicit_conditions.values()):
        sections.append({"name": "Conditions", "kind": "conditions", "summary": None, "page_number": None, "attributes": {}})
    for label, value in explicit_conditions.items():
        if not value:
            continue
        normalized = normalize_entity(
            {"label": label, "valueText": str(value), "status": str(value)},
            default_entity_type="condition",
            default_category="diagnosis",
            default_section="Conditions",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for other_condition in coerce_string_list(conditions.get("otherConditions")):
        normalized = normalize_entity(
            {"label": other_condition},
            default_entity_type="condition",
            default_category="diagnosis",
            default_section="Conditions",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)

    medications = parsed_report.get("medications", []) or []
    if medications:
        sections.append({"name": "Medications", "kind": "medications", "summary": None, "page_number": None, "attributes": {}})
    for medication in medications:
        normalized = normalize_entity(
            medication,
            default_entity_type="medication",
            default_category="prescription",
            default_section="Medications",
            default_date=report_date,
        )
        if normalized:
            if not normalized.get("value_text") and isinstance(medication, dict):
                dose = coerce_string(medication.get("dose") or medication.get("dosage"))
                schedule = coerce_string(medication.get("schedule"))
                timing = coerce_string(medication.get("timing"))
                bits = [bit for bit in [dose, schedule, timing] if bit]
                normalized["value_text"] = "; ".join(bits) if bits else None
                normalized["attributes"]["with_food"] = medication.get("withFood")
            entities.append(normalized)

    for restriction in coerce_string_list(parsed_report.get("dietaryRestrictions")):
        normalized = normalize_entity(
            {"label": restriction},
            default_entity_type="restriction",
            default_category="diet",
            default_section="Restrictions",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for preference in coerce_string_list(parsed_report.get("dietaryPreferences")):
        normalized = normalize_entity(
            {"label": preference, "category": "diet_preference"},
            default_entity_type="restriction",
            default_category="diet_preference",
            default_section="Restrictions",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for allergy in coerce_string_list(parsed_report.get("allergies")):
        normalized = normalize_entity(
            {"label": allergy},
            default_entity_type="allergy",
            default_category="allergy",
            default_section="Allergies",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for advice in coerce_string_list(parsed_report.get("doctorAdvice")):
        normalized = normalize_entity(
            {"label": advice},
            default_entity_type="recommendation",
            default_category="advice",
            default_section="Doctor Advice",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for finding in coerce_string_list(parsed_report.get("clinicalFindings")):
        normalized = normalize_entity(
            {"label": finding},
            default_entity_type="finding",
            default_category="clinical_finding",
            default_section="Clinical Findings",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)
    for impression in coerce_string_list(parsed_report.get("diagnosticImpressions")):
        normalized = normalize_entity(
            {"label": impression, "category": "diagnostic_impression"},
            default_entity_type="finding",
            default_category="diagnostic_impression",
            default_section="Diagnostic Impressions",
            default_date=report_date,
        )
        if normalized:
            entities.append(normalized)

    return entities, sections


def infer_document_type(title: Optional[str], sections: List[Dict[str, Any]], entities: List[Dict[str, Any]]) -> str:
    text_blocks = [title or ""]
    text_blocks.extend(filter(None, [section.get("name") for section in sections]))
    text_blocks.extend(filter(None, [section.get("summary") for section in sections]))
    text_blocks.extend(filter(None, [entity.get("label") for entity in entities[:20]]))

    joined = " ".join(text_blocks).lower()
    for document_type, patterns in DOCUMENT_TYPE_HINTS.items():
        if any(re.search(pattern, joined) for pattern in patterns):
            return document_type

    category_counts: Dict[str, int] = {}
    for entity in entities:
        category = entity.get("category") or entity.get("entity_type") or "other"
        category_counts[category] = category_counts.get(category, 0) + 1

    if category_counts.get("prescription", 0) >= 2:
        return "prescription"
    if category_counts.get("lab", 0) >= 2 or category_counts.get("observation", 0) >= 3:
        return "lab_report"
    if category_counts.get("diagnosis", 0) >= 1 and category_counts.get("advice", 0) >= 1:
        return "consultation_note"
    return "unknown"


def normalize_dynamic_report(parsed_report: Dict[str, Any]) -> Dict[str, Any]:
    parsed_report = parsed_report if isinstance(parsed_report, dict) else {}
    reparsed_payload = None
    if parsed_report.get("raw_text") and not any(
        parsed_report.get(key) for key in ("entities", "sections", "result", "conditions", "medications")
    ):
        reparsed_payload = parse_llm_json_payload(parsed_report.get("raw_text"))
    if isinstance(reparsed_payload, dict):
        parsed_report = reparsed_payload

    title = coerce_string(parsed_report.get("title") or parsed_report.get("reportTitle") or parsed_report.get("resourceType"))
    report_date = parse_report_date(
        coerce_string(
            parsed_report.get("reportDate")
            or parsed_report.get("report_date")
            or parsed_report.get("effectiveDateTime")
            or parsed_report.get("effective_date")
        )
    )

    sections = [
        section
        for section in (
            normalize_section(item, fallback_name=f"Section {idx + 1}")
            for idx, item in enumerate(parsed_report.get("sections", []) or [])
        )
        if section
    ]

    direct_entities = [
        entity
        for entity in (
            normalize_entity(item, default_date=report_date)
            for item in parsed_report.get("entities", []) or []
        )
        if entity
    ]

    if direct_entities:
        entities = direct_entities
        legacy_sections = []
    else:
        entities, legacy_sections = extract_legacy_entities(parsed_report)
        if not sections:
            sections = legacy_sections

    unmapped_entities: List[Dict[str, Any]] = []
    for item in parsed_report.get("unmappedEntities", []) or parsed_report.get("unmapped_entities", []) or []:
        normalized = normalize_entity(item, default_entity_type="other", default_category="unmapped", default_date=report_date)
        if normalized:
            unmapped_entities.append(normalized)

    for item in parsed_report.get("unmappedText", []) or parsed_report.get("unmapped_text", []) or []:
        normalized = normalize_entity(
            {"label": item},
            default_entity_type="other",
            default_category="unmapped",
            default_date=report_date,
        )
        if normalized:
            unmapped_entities.append(normalized)

    raw_text = coerce_string(parsed_report.get("raw_text"))
    if raw_text and not entities and not unmapped_entities:
        normalized = normalize_entity(
            {"label": raw_text},
            default_entity_type="other",
            default_category="unmapped",
            default_date=report_date,
        )
        if normalized:
            unmapped_entities.append(normalized)

    source_documents = []
    for item in parsed_report.get("sourceDocuments", []) or parsed_report.get("source_documents", []) or []:
        if not isinstance(item, dict):
            continue
        source_documents.append(
            {
                "filename": coerce_string(item.get("filename")),
                "document_type": coerce_string(item.get("document_type") or item.get("documentType")),
                "report_date": coerce_string(item.get("report_date") or item.get("reportDate")),
                "entity_count": _coerce_int(item.get("entity_count") or item.get("entityCount")) or 0,
            }
        )

    document_type = coerce_string(parsed_report.get("documentType") or parsed_report.get("document_type"))
    if not document_type:
        document_type = infer_document_type(title, sections, entities)

    return {
        "documentType": document_type,
        "title": title or "Medical report",
        "reportDate": report_date.isoformat() if report_date else None,
        "sections": [json_safe_value(section) for section in sections],
        "entities": [json_safe_value(entity) for entity in entities],
        "unmappedEntities": [json_safe_value(entity) for entity in unmapped_entities],
        "sourceDocuments": source_documents,
    }


def merge_dynamic_reports(parsed_reports: List[Dict[str, Any]], filenames: Optional[List[str]] = None) -> Dict[str, Any]:
    normalized_reports = [normalize_dynamic_report(report) for report in parsed_reports if isinstance(report, dict)]
    if not normalized_reports:
        return normalize_dynamic_report({})

    combined_entities: List[Dict[str, Any]] = []
    combined_sections: List[Dict[str, Any]] = []
    combined_unmapped: List[Dict[str, Any]] = []
    source_documents: List[Dict[str, Any]] = []
    report_dates: List[date] = []
    document_types = set()

    for index, report in enumerate(normalized_reports):
        filename = filenames[index] if filenames and index < len(filenames) else None
        document_type = report.get("documentType") or "unknown"
        if document_type:
            document_types.add(document_type)
        report_date = parse_report_date(report.get("reportDate"))
        if report_date:
            report_dates.append(report_date)

        source_documents.append(
            {
                "filename": filename,
                "document_type": document_type,
                "report_date": report.get("reportDate"),
                "entity_count": len(report.get("entities", [])),
                "unmapped_entity_count": len(report.get("unmappedEntities", [])),
            }
        )

        for section in report.get("sections", []):
            section_copy = dict(section)
            attributes = dict(section_copy.get("attributes") or {})
            if filename:
                attributes.setdefault("source_filename", filename)
            section_copy["attributes"] = attributes
            combined_sections.append(section_copy)

        for collection, target in (
            (report.get("entities", []), combined_entities),
            (report.get("unmappedEntities", []), combined_unmapped),
        ):
            for entity in collection:
                entity_copy = dict(entity)
                attributes = dict(entity_copy.get("attributes") or {})
                if filename:
                    attributes.setdefault("source_filename", filename)
                attributes.setdefault("source_document_type", document_type)
                entity_copy["attributes"] = attributes
                target.append(entity_copy)

    latest_date = max(report_dates).isoformat() if report_dates else None
    combined_type = document_types.pop() if len(document_types) == 1 else "multi_document_bundle"
    title = "Combined medical upload" if len(normalized_reports) > 1 else normalized_reports[0].get("title", "Medical report")

    return {
        "documentType": combined_type,
        "title": title,
        "reportDate": latest_date,
        "sections": combined_sections,
        "entities": combined_entities,
        "unmappedEntities": combined_unmapped,
        "sourceDocuments": source_documents,
    }


def _entity_text(entity: Dict[str, Any]) -> str:
    return " ".join(
        bit
        for bit in [
            entity.get("label"),
            entity.get("value_text"),
            entity.get("status"),
            entity.get("interpretation"),
            entity.get("source_text"),
        ]
        if bit
    )


def _is_observation_entity(entity: Dict[str, Any]) -> bool:
    if entity.get("entity_type") != "observation":
        return False
    if entity.get("value_text") or entity.get("value_numeric") is not None:
        return True
    return bool(entity.get("canonical_name"))


def build_structured_report(parsed_report: Dict[str, Any]) -> Dict[str, Any]:
    dynamic_report = normalize_dynamic_report(parsed_report)
    entities = dynamic_report.get("entities", []) or []
    unmapped_entities = dynamic_report.get("unmappedEntities", []) or []
    sections = dynamic_report.get("sections", []) or []

    findings_text = [_entity_text(entity) for entity in entities + unmapped_entities]
    findings_text.extend(filter(None, [section.get("summary") for section in sections]))
    findings_text = [item for item in findings_text if item]

    snapshot = {
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

    labs: List[Dict[str, Any]] = []
    medications: List[Dict[str, Any]] = []

    for entity in entities:
        entity_type = entity.get("entity_type")
        category = entity.get("category")
        label = entity.get("label")
        value_text = entity.get("value_text")
        status = entity.get("status")
        entity_text = _entity_text(entity)

        if entity_type == "condition":
            canonical_condition = entity.get("canonical_name") or canonical_condition_name(entity_text)
            normalized = normalize_status(status or value_text)
            if canonical_condition == "diabetes" and (
                snapshot["diabetes_status"] == "unknown" or normalized != "unknown"
            ):
                snapshot["diabetes_status"] = normalized if normalized != "unknown" else "yes"
            elif canonical_condition == "hypertension" and (
                snapshot["hypertension_status"] == "unknown" or normalized != "unknown"
            ):
                snapshot["hypertension_status"] = normalized if normalized != "unknown" else "yes"
            elif canonical_condition == "dyslipidemia" and (
                snapshot["dyslipidemia_status"] == "unknown" or normalized != "unknown"
            ):
                snapshot["dyslipidemia_status"] = normalized if normalized != "unknown" else "yes"
            elif canonical_condition == "kidney_disease":
                if value_text and "stage" in value_text.lower():
                    snapshot["kidney_disease_stage"] = value_text
                else:
                    stage_match = re.search(r"stage\s*([0-9a-zA-Z -]+)", entity_text, re.IGNORECASE)
                    snapshot["kidney_disease_stage"] = stage_match.group(1).strip() if stage_match else value_text or label
            elif label:
                snapshot["extra_conditions"].append(label)

        elif entity_type == "restriction":
            restriction_value = label or value_text
            if restriction_value:
                if category == "diet_preference":
                    snapshot["dietary_preferences"].append(restriction_value)
                else:
                    snapshot["food_restrictions"].append(restriction_value)

        elif entity_type == "allergy":
            allergy_value = label or value_text
            if allergy_value:
                snapshot["allergies"].append(allergy_value)

        elif entity_type == "recommendation":
            advice_value = label or value_text
            if advice_value:
                snapshot["doctor_advice"].append(advice_value)

        elif entity_type == "medication":
            dosage = entity.get("attributes", {}).get("dose") or entity.get("attributes", {}).get("dosage")
            schedule = entity.get("attributes", {}).get("schedule")
            timing_notes = entity.get("attributes", {}).get("timing") or entity.get("attributes", {}).get("timing_notes")
            medications.append(
                {
                    "medication_name": label or "Unknown medication",
                    "dosage": coerce_string(dosage) or value_text,
                    "schedule": coerce_string(schedule),
                    "timing_notes": coerce_string(timing_notes),
                    "with_food": entity.get("attributes", {}).get("with_food"),
                }
            )

        if _is_observation_entity(entity):
            numeric_value = entity.get("value_numeric")
            if numeric_value is None and value_text:
                numeric_value, _ = extract_numeric(value_text)
            labs.append(
                {
                    "test_name": label or "Unknown observation",
                    "canonical_name": entity.get("canonical_name") or canonical_lab_name(label or value_text),
                    "value_numeric": numeric_value,
                    "value_text": value_text or label or "Not provided",
                    "unit": entity.get("unit"),
                    "reference_range": entity.get("reference_range"),
                    "interpretation": entity.get("interpretation"),
                    "abnormal_flag": entity.get("status") or entity.get("interpretation"),
                }
            )

    if snapshot["diabetes_status"] == "unknown":
        snapshot["diabetes_status"] = contains_condition(findings_text, "diabetes")
    if snapshot["hypertension_status"] == "unknown":
        snapshot["hypertension_status"] = contains_condition(findings_text, "hypertension")
    if snapshot["dyslipidemia_status"] == "unknown":
        snapshot["dyslipidemia_status"] = contains_condition(findings_text, "dyslipidemia")
    if not snapshot["kidney_disease_stage"]:
        for block in findings_text:
            match = re.search(r"(?:kidney disease|ckd|renal disease).{0,20}?stage\s*([0-9a-zA-Z -]+)", block, re.IGNORECASE)
            if match:
                snapshot["kidney_disease_stage"] = match.group(1).strip()
                break

    snapshot["food_restrictions"] = sorted(set(snapshot["food_restrictions"]))
    snapshot["allergies"] = sorted(set(snapshot["allergies"]))
    snapshot["dietary_preferences"] = sorted(set(snapshot["dietary_preferences"]))
    snapshot["doctor_advice"] = sorted(set(snapshot["doctor_advice"]))
    snapshot["extra_conditions"] = sorted(set(snapshot["extra_conditions"]))

    return {
        "document_type": dynamic_report.get("documentType"),
        "report_date": parse_report_date(dynamic_report.get("reportDate")),
        "sections": sections,
        "entities": entities,
        "unmapped_entities": unmapped_entities,
        "snapshot": snapshot,
        "labs": labs,
        "medications": medications,
    }


def build_health_context_summary(snapshot: Dict[str, Any], labs: List[Dict[str, Any]], medications: List[Dict[str, Any]]) -> str:
    lab_summary_bits = []
    for lab in labs[:6]:
        if lab.get("canonical_name"):
            label = lab["canonical_name"].replace("_", " ").upper()
        else:
            label = lab.get("test_name", "Observation")
        lab_summary_bits.append(f"{label}: {lab.get('value_text')}")

    medication_bits = [item["medication_name"] for item in medications if item.get("medication_name")]
    restrictions = snapshot.get("food_restrictions") or []
    advice = snapshot.get("doctor_advice") or []
    extra_conditions = snapshot.get("extra_conditions") or []

    parts = [
        f"Diabetes: {snapshot.get('diabetes_status', 'unknown')}",
        f"Hypertension: {snapshot.get('hypertension_status', 'unknown')}",
        f"Kidney disease stage: {snapshot.get('kidney_disease_stage') or 'not stated'}",
        f"Dyslipidemia: {snapshot.get('dyslipidemia_status', 'unknown')}",
    ]
    if extra_conditions:
        parts.append("Other conditions: " + ", ".join(extra_conditions[:6]))
    if lab_summary_bits:
        parts.append("Recent observations: " + "; ".join(lab_summary_bits))
    if restrictions:
        parts.append("Food restrictions: " + ", ".join(restrictions))
    if medication_bits:
        parts.append("Medications: " + ", ".join(medication_bits))
    if advice:
        parts.append("Doctor advice: " + "; ".join(advice))
    return "\n".join(parts)


def group_food_items_for_review(fooditems: Any) -> Dict[str, Any]:
    reviewed_items = []
    warnings = []

    if isinstance(fooditems, dict):
        normalized_items = fooditems.get("fooditem_details") or fooditems.get("fooditems") or []
    else:
        normalized_items = fooditems or []

    for item in normalized_items:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            quantity = coerce_string(item.get("quantity"))
            preparation = coerce_string(item.get("preparation"))
            source_label = coerce_string(item.get("source_label")) or name
            confidence = item.get("confidence")
        else:
            name = str(item).strip()
            quantity = None
            preparation = None
            source_label = name
            confidence = None

        if not name:
            continue

        role = "main"
        lowered = name.lower()
        for candidate_role, patterns in ROLE_PATTERNS.items():
            if any(re.search(pattern, lowered) for pattern in patterns):
                role = candidate_role
                break

        if role in {"condiment", "side"}:
            warnings.append(
                f"Review '{name}' to confirm it is a separate serving and not just part of the main meal."
            )

        reviewed_items.append(
            {
                "name": name,
                "quantity": quantity,
                "role": role,
                "preparation": preparation,
                "source_label": source_label,
                "confidence": confidence,
                "editable": True,
            }
        )

    meal_title = ", ".join([item["name"] for item in reviewed_items if item["role"] == "main"][:2]) or "Meal draft"
    return {
        "meal_title": meal_title,
        "items": reviewed_items,
        "warnings": sorted(set(warnings)),
    }


def parse_vitals_csv(content: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    required = {"captured_at", "vital_type", "value_primary", "unit"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV must contain captured_at, vital_type, value_primary, and unit columns")

    records = []
    for row in reader:
        captured_at = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
        value_secondary = row.get("value_secondary")
        records.append(
            {
                "captured_at": captured_at,
                "vital_type": row["vital_type"],
                "value_primary": Decimal(row["value_primary"]),
                "value_secondary": Decimal(value_secondary) if value_secondary else None,
                "unit": row["unit"],
                "notes": row.get("notes"),
                "metadata": {},
            }
        )
    return records
