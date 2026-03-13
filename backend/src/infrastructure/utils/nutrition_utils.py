"""
Helpers for consistent nutrition metric parsing and formatting.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional


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


def normalize_nutrition_metric(value: Any, default_unit: str) -> dict[str, Any]:
    if isinstance(value, dict):
        raw_value = value.get("value")
        numeric_value = _coerce_float(raw_value)
        inferred_unit = None
        if numeric_value is None and isinstance(raw_value, str):
            match = re.search(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z%/._-]+)?", raw_value.strip())
            if match:
                numeric_value = float(match.group(1))
                inferred_unit = match.group(2)
        unit = str(value.get("unit") or inferred_unit or default_unit).strip()
        if numeric_value is None:
            raise ValueError("Nutrition metric value is required")
        return {"value": numeric_value, "unit": unit}

    numeric_value = _coerce_float(value)
    if numeric_value is not None:
        return {"value": numeric_value, "unit": default_unit}

    if isinstance(value, str):
        text = value.strip()
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*([A-Za-z%/._-]+)?", text)
        if match:
            numeric_value = float(match.group(1))
            unit = match.group(2) or default_unit
            return {"value": numeric_value, "unit": unit}

    raise ValueError(f"Unable to parse nutrition metric from: {value!r}")


def metric_value(value: Any, default_unit: Optional[str] = None) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, dict):
        return _coerce_float(value.get("value"))
    numeric_value = _coerce_float(value)
    if numeric_value is not None:
        return numeric_value
    if isinstance(value, str):
        match = re.search(r"(-?\d+(?:\.\d+)?)", value.strip())
        if match:
            return float(match.group(1))
    return None


def format_metric(value: Any, default_unit: str) -> str:
    try:
        normalized = normalize_nutrition_metric(value, default_unit)
    except ValueError:
        return str(value)
    numeric_value = normalized["value"]
    if float(numeric_value).is_integer():
        rendered_value = str(int(numeric_value))
    else:
        rendered_value = f"{numeric_value:.2f}".rstrip("0").rstrip(".")
    return f"{rendered_value} {normalized['unit']}"


def extract_food_item_names(food_analysis: Any) -> list[str]:
    if isinstance(food_analysis, dict):
        details = food_analysis.get("fooditem_details")
        if isinstance(details, list):
            names = [
                str(item.get("name")).strip()
                for item in details
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            if names:
                return names

        fooditems = food_analysis.get("fooditems")
        if isinstance(fooditems, list):
            return [str(item).strip() for item in fooditems if str(item).strip()]

    if isinstance(food_analysis, list):
        if food_analysis and all(isinstance(item, dict) for item in food_analysis):
            return [
                str(item.get("name")).strip()
                for item in food_analysis
                if str(item.get("name") or "").strip()
            ]
        return [str(item).strip() for item in food_analysis if str(item).strip()]

    return []


def format_food_analysis_summary(food_analysis: Any) -> str:
    if isinstance(food_analysis, dict):
        details = food_analysis.get("fooditem_details")
        if isinstance(details, list) and details:
            formatted_items = []
            for item in details:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                parts = []
                quantity = str(item.get("quantity") or "").strip()
                preparation = str(item.get("preparation") or "").strip()
                if quantity:
                    parts.append(quantity)
                if preparation:
                    parts.append(preparation)
                if parts:
                    formatted_items.append(f"{name} ({'; '.join(parts)})")
                else:
                    formatted_items.append(name)
            if formatted_items:
                return ", ".join(formatted_items)

    names = extract_food_item_names(food_analysis)
    return ", ".join(names) if names else "No food items identified"
