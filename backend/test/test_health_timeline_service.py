from src.application.services.health_utils import (
    build_structured_report,
    group_food_items_for_review,
    group_report_analyses_by_category,
    infer_report_category,
    merge_dynamic_reports,
    normalize_dynamic_report,
    parse_llm_json_payload,
    parse_vitals_csv,
)


def test_build_structured_report_maps_conditions_and_labs():
    parsed_report = {
        "effectiveDateTime": "2026-03-01",
        "conditions": {
            "diabetes": "yes",
            "hypertension": "unknown",
            "kidneyDiseaseStage": "Stage 2",
            "dyslipidemia": "yes",
            "otherConditions": ["fatty liver"],
        },
        "dietaryRestrictions": ["low sodium", "halal"],
        "doctorAdvice": ["Reduce refined carbs"],
        "medications": [
            {
                "name": "Metformin",
                "dose": "500 mg",
                "schedule": "twice daily",
                "timing": "after meals",
                "withFood": True,
            }
        ],
        "result": [
            {
                "testName": "HbA1c",
                "value": "7.2 %",
                "referenceRange": "4.0-5.6%",
                "interpretation": "high",
            },
            {
                "testName": "LDL Cholesterol",
                "value": "145 mg/dL",
                "referenceRange": "<100 mg/dL",
            },
        ],
    }

    structured = build_structured_report(parsed_report)

    assert structured["snapshot"]["diabetes_status"] == "yes"
    assert structured["snapshot"]["kidney_disease_stage"] == "Stage 2"
    assert "halal" in structured["snapshot"]["food_restrictions"]
    assert structured["medications"][0]["medication_name"] == "Metformin"
    assert structured["labs"][0]["canonical_name"] == "hba1c"
    assert float(structured["labs"][1]["value_numeric"]) == 145.0


def test_group_food_items_for_review_flags_possible_sides():
    grouped = group_food_items_for_review(
        ["pizza with cheese and tomato", "salad", "garlic sauce", "cola"]
    )

    roles = {item["name"]: item["role"] for item in grouped["items"]}
    assert roles["pizza with cheese and tomato"] == "main"
    assert roles["salad"] == "side"
    assert roles["garlic sauce"] == "condiment"
    assert roles["cola"] == "beverage"
    assert grouped["warnings"]


def test_group_food_items_for_review_preserves_detail_metadata():
    grouped = group_food_items_for_review(
        {
            "fooditem_details": [
                {
                    "name": "palak pakora",
                    "quantity": "4 pieces",
                    "preparation": "fried",
                    "confidence": 0.92,
                },
                {
                    "name": "mint chutney",
                    "quantity": "2 tbsp",
                },
            ]
        }
    )

    assert grouped["items"][0]["quantity"] == "4 pieces"
    assert grouped["items"][0]["preparation"] == "fried"
    assert grouped["items"][0]["confidence"] == 0.92
    assert grouped["items"][1]["role"] == "condiment"


def test_parse_vitals_csv_reads_required_fields():
    csv_content = """captured_at,vital_type,value_primary,value_secondary,unit,notes
2026-03-10T13:30:00+00:00,cgm,168,,mg/dL,post lunch
2026-03-10T15:00:00+00:00,blood_pressure,142,92,mmHg,afternoon
"""

    entries = parse_vitals_csv(csv_content)

    assert len(entries) == 2
    assert entries[0]["vital_type"] == "cgm"
    assert float(entries[1]["value_secondary"]) == 92.0


def test_normalize_dynamic_report_preserves_unknown_entities_and_sections():
    parsed_report = {
        "documentType": "unknown",
        "title": "Outside hospital note",
        "reportDate": "2026-03-05",
        "sections": [
            {
                "name": "Assessment",
                "kind": "other",
                "summary": "Patient complains of fatigue and dizziness",
                "pageNumber": 1,
            }
        ],
        "entities": [
            {
                "entityType": "observation",
                "category": "lab",
                "label": "Serum Ferritin",
                "valueText": "18 ng/mL",
                "referenceRange": "30-400",
                "sourceSection": "Assessment",
            },
            {
                "entityType": "other",
                "label": "Sleep duration",
                "valueText": "5 hours",
                "sourceText": "Sleeping 5 hours per night",
            },
        ],
        "unmappedEntities": [
            {
                "label": "Follow up in 2 weeks",
                "sourceText": "Review after two weeks",
            }
        ],
    }

    normalized = normalize_dynamic_report(parsed_report)
    structured = build_structured_report(normalized)

    assert normalized["documentType"] == "unknown"
    assert normalized["sections"][0]["name"] == "Assessment"
    assert len(normalized["entities"]) == 2
    assert normalized["unmappedEntities"][0]["label"] == "Follow up in 2 weeks"
    assert structured["labs"][0]["canonical_name"] is None
    assert structured["entities"][1]["label"] == "Sleep duration"


def test_merge_dynamic_reports_combines_files_without_dropping_unknown_content():
    report_a = {
        "documentType": "lab_report",
        "reportDate": "2026-03-01",
        "entities": [
            {
                "entityType": "observation",
                "category": "lab",
                "label": "HbA1c",
                "valueText": "7.1 %",
            }
        ],
    }
    report_b = {
        "documentType": "consultation_note",
        "reportDate": "2026-03-10",
        "entities": [
            {
                "entityType": "recommendation",
                "label": "Avoid sugary drinks",
            }
        ],
        "unmappedEntities": [
            {
                "label": "Patient reports stress eating at night",
            }
        ],
    }

    merged = merge_dynamic_reports([report_a, report_b], filenames=["lab.pdf", "note.jpg"])
    structured = build_structured_report(merged)

    assert merged["documentType"] == "multi_document_bundle"
    assert merged["reportDate"] == "2026-03-10"
    assert len(merged["sourceDocuments"]) == 2
    assert merged["entities"][0]["attributes"]["source_filename"] == "lab.pdf"
    assert merged["unmappedEntities"][0]["attributes"]["source_filename"] == "note.jpg"
    assert "Avoid sugary drinks" in structured["snapshot"]["doctor_advice"]


def test_parse_llm_json_payload_handles_fenced_json():
    fenced = """```json
{
  "documentType": "lab_report",
  "reportDate": "2026-03-12",
  "entities": [
    {
      "entityType": "observation",
      "category": "lab",
      "label": "TSH",
      "valueText": "2.5 uIU/mL"
    }
  ]
}
```"""

    parsed = parse_llm_json_payload(fenced)
    normalized = normalize_dynamic_report({"raw_text": fenced})

    assert parsed["documentType"] == "lab_report"
    assert normalized["entities"][0]["label"] == "TSH"


def test_infer_report_category_detects_mixed_lab_panel_scope():
    report = normalize_dynamic_report(
        {
            "documentType": "lab_report",
            "title": "Comprehensive metabolic and lipid panel",
            "entities": [
                {
                    "entityType": "observation",
                    "category": "lab",
                    "label": "HbA1c",
                    "valueText": "7.4 %",
                },
                {
                    "entityType": "observation",
                    "category": "lab",
                    "label": "LDL Cholesterol",
                    "valueText": "145 mg/dL",
                },
            ],
        }
    )

    category_meta = infer_report_category(report)

    assert category_meta["primary_category"] == "lab_panel"
    assert category_meta["category_scopes"] == ["lipid", "metabolic"]


def test_group_report_analyses_by_category_separates_thyroid_from_metabolic_uploads():
    grouped = group_report_analyses_by_category(
        [
            {
                "filename": "a1c.pdf",
                "analysis": {
                    "documentType": "lab_report",
                    "entities": [
                        {
                            "entityType": "observation",
                            "category": "lab",
                            "label": "HbA1c",
                            "valueText": "7.2 %",
                        }
                    ],
                },
            },
            {
                "filename": "thyroid.pdf",
                "analysis": {
                    "documentType": "lab_report",
                    "entities": [
                        {
                            "entityType": "observation",
                            "category": "lab",
                            "label": "TSH",
                            "valueText": "2.5 uIU/mL",
                        }
                    ],
                },
            },
        ]
    )

    categories = [item["report_category"] for item in grouped]

    assert categories == ["metabolic", "thyroid"]
    assert grouped[0]["filenames"] == ["a1c.pdf"]
    assert grouped[1]["filenames"] == ["thyroid.pdf"]
