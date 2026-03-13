# DietGuard API Reference

Last updated: March 13, 2026

## Overview

Base URL for local development:

- `http://localhost:8000`

Interactive docs:

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Health check: `/health`

Canonical API prefix:

- `/api/v1`

Recommended usage:

- Prefer `/api/v1/*` endpoints for new client work.
- Treat older root-level endpoints and deprecated `/api/v1/ai/get-*` endpoints as compatibility paths only.

## Authentication

JWT bearer authentication is required for most endpoints outside signup/signin and public package listing.

Auth header:

```http
Authorization: Bearer <access_token>
```

Authentication endpoints:

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/signup` | No | Creates user + patient profile data |
| `POST` | `/api/v1/auth/signin` | No | Returns access + refresh token |
| `POST` | `/api/v1/auth/refresh-token` | No | Exchanges refresh token for new access token |
| `POST` | `/api/v1/auth/forgot-password` | No | Starts password reset |
| `POST` | `/api/v1/auth/reset-password` | No | Completes password reset |
| `DELETE` | `/api/v1/auth/delete-account` | Yes | Deletes current account |

## Core Data Contracts

### Food analysis contract

Public food-analysis responses now use `fooditem_details` as the item-level source of truth.

```json
{
  "food_analysis": {
    "fooditem_details": [
      {
        "name": "pizza with cheese and tomato",
        "quantity": "2 slices",
        "preparation": "baked",
        "nutrition": {
          "calories": { "value": 320, "unit": "kcal" },
          "protein": { "value": 12, "unit": "g" },
          "carbohydrates": { "value": 38, "unit": "g" },
          "fat": { "value": 14, "unit": "g" },
          "fiber": { "value": 2, "unit": "g" },
          "sugar": { "value": 4, "unit": "g" }
        }
      }
    ],
    "nutrition": {
      "calories": { "value": 650, "unit": "kcal" },
      "protein": { "value": 45, "unit": "g" },
      "carbohydrates": { "value": 58, "unit": "g" },
      "fat": { "value": 26, "unit": "g" },
      "fiber": { "value": 3, "unit": "g" },
      "sugar": { "value": 6, "unit": "g" }
    }
  }
}
```

Important:

- Do not rely on `fooditems[]` in new client code.
- Nutrition metrics use `{ value, unit }`, not raw strings like `"12g"`.

### Dynamic medical report contract

Medical report parsing is dynamic. The normalized report payload may include:

```json
{
  "documentType": "lab_report",
  "title": "Lipid Profile Report",
  "reportDate": "2026-03-10",
  "sections": [
    {
      "name": "Lipid Profile",
      "kind": "lab_panel",
      "summary": "Cholesterol panel",
      "pageNumber": 1
    }
  ],
  "entities": [
    {
      "entityType": "observation",
      "category": "lab",
      "label": "LDL Cholesterol",
      "valueText": "145 mg/dL",
      "referenceRange": "<100 mg/dL",
      "interpretation": "high"
    }
  ],
  "unmappedEntities": []
}
```

The backend also derives a structured health profile from these dynamic entities for downstream food/vitals logic.

## AI Endpoints

### Food, reports, and nutrition

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/ai/upload-food` | Yes | Food image analysis with item-level + total nutrition |
| `POST` | `/api/v1/ai/scan-ingredients` | Yes | Ingredient scan from packaging image |
| `POST` | `/api/v1/ai/upload-report` | Yes | Dynamic medical report parsing + structured sync |
| `POST` | `/api/v1/ai/nutrition-advice` | Yes | Nutritionist advice using food analysis + patient context |
| `POST` | `/api/v1/ai/calculate-nutrition` | Yes | Recalculate nutrition from edited food item text |
| `GET` | `/api/v1/ai/report-data` | Yes | Current saved report payload |
| `DELETE` | `/api/v1/ai/report-data` | Yes | Delete saved report payload |
| `GET` | `/api/v1/ai/nutrition-data` | Yes | Nutrition history / saved nutrition data |
| `GET` | `/api/v1/ai/nutrition-data/today` | Yes | Today's nutrition records |

#### `POST /api/v1/ai/upload-food`

Request:

- `multipart/form-data`
- `files[]`: one or more `.jpg`, `.jpeg`, `.png`

Response highlights:

- `user_email`
- `files_processed`
- `filenames`
- `food_analysis.fooditem_details[]`
- `food_analysis.nutrition`

#### `POST /api/v1/ai/scan-ingredients`

Request:

- `multipart/form-data`
- `file`: one packaging image

Response highlights:

- ingredient list
- health ratings
- allergen flags
- dietary compatibility flags
- critical warnings

#### `POST /api/v1/ai/upload-report`

Request:

- `multipart/form-data`
- `files[]`: `.jpg`, `.jpeg`, `.png`, `.pdf`

Response highlights:

- `files_processed`
- `filenames`
- `ehr_data` dynamic normalized report payload
- `version`
- `uploaded_at`
- `structured_health_profile`

#### `POST /api/v1/ai/nutrition-advice`

Request body:

```json
{
  "food_analysis": {
    "fooditem_details": [
      {
        "name": "grilled chicken with rice",
        "quantity": "1 plate",
        "preparation": "grilled",
        "nutrition": {
          "calories": { "value": 520, "unit": "kcal" },
          "protein": { "value": 35, "unit": "g" },
          "carbohydrates": { "value": 48, "unit": "g" },
          "fat": { "value": 14, "unit": "g" },
          "fiber": { "value": 3, "unit": "g" },
          "sugar": { "value": 2, "unit": "g" }
        }
      }
    ],
    "nutrition": {
      "calories": { "value": 520, "unit": "kcal" },
      "protein": { "value": 35, "unit": "g" },
      "carbohydrates": { "value": 48, "unit": "g" },
      "fat": { "value": 14, "unit": "g" },
      "fiber": { "value": 3, "unit": "g" },
      "sugar": { "value": 2, "unit": "g" }
    }
  },
  "meal_type": "lunch",
  "meal_time": "13:00",
  "meal_date": "2026-03-13"
}
```

Response highlights:

- `user_email`
- `meal_type`
- `meal_info`
- `nutritionist_recommendations`

#### `POST /api/v1/ai/calculate-nutrition`

Request body:

```json
{
  "fooditems": [
    "2 slices pizza with cheese and tomato",
    "1 grilled chicken breast"
  ],
  "old_food_analysis": {
    "fooditem_details": [
      {
        "name": "pizza with cheese and tomato",
        "quantity": "2 slices",
        "nutrition": {
          "calories": { "value": 320, "unit": "kcal" },
          "protein": { "value": 12, "unit": "g" },
          "carbohydrates": { "value": 38, "unit": "g" },
          "fat": { "value": 14, "unit": "g" },
          "fiber": { "value": 2, "unit": "g" },
          "sugar": { "value": 4, "unit": "g" }
        }
      }
    ],
    "nutrition": {
      "calories": { "value": 320, "unit": "kcal" },
      "protein": { "value": 12, "unit": "g" },
      "carbohydrates": { "value": 38, "unit": "g" },
      "fat": { "value": 14, "unit": "g" },
      "fiber": { "value": 2, "unit": "g" },
      "sugar": { "value": 4, "unit": "g" }
    }
  }
}
```

Response highlights:

- `food_analysis.fooditem_details[]`
- `food_analysis.nutrition`

Request note:

- `fooditems[]` is still used here as the edited user input list for recalculation.
- The response contract does not require `fooditems[]`.

## Health Timeline Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health/profile/current` | Yes | Current structured health profile |
| `POST` | `/api/v1/health/meals/draft-from-image` | Yes | Draft meal items from uploaded image(s) |
| `POST` | `/api/v1/health/meals/confirm` | Yes | Confirm edited meal and persist event |
| `POST` | `/api/v1/health/vitals` | Yes | Create manual vital entries |
| `POST` | `/api/v1/health/vitals/import-csv` | Yes | Bulk import vitals from CSV |
| `POST` | `/api/v1/health/vitals/device-sync` | Yes | Generic device-sync vital ingestion |
| `GET` | `/api/v1/health/insights/daily` | Yes | Daily summary/correlation payload |
| `GET` | `/api/v1/health/insights/weekly` | Yes | Weekly summary/correlation payload |

### `GET /api/v1/health/profile/current`

Returns:

- current report metadata
- structured condition snapshot
- normalized labs
- medications
- dynamic entities
- sections
- unmapped entities
- lab trends
- health context summary

### `POST /api/v1/health/meals/draft-from-image`

Request:

- `multipart/form-data`
- `files[]`: meal images

Returns:

- `meal_title`
- editable `items[]`
- `warnings[]`
- `filenames[]`
- `raw_food_analysis`

### `POST /api/v1/health/meals/confirm`

Request body:

```json
{
  "meal_type": "lunch",
  "meal_time": "13:00",
  "meal_date": "2026-03-13",
  "items": [
    {
      "name": "pizza with cheese and tomato",
      "quantity": "2 slices",
      "role": "main",
      "preparation": "baked"
    }
  ],
  "source_filenames": ["meal.jpg"],
  "notes": "User-confirmed meal"
}
```

Returns:

- `meal_event_id`
- confirmed `food_analysis` with `fooditem_details` and total `nutrition`

### `POST /api/v1/health/vitals`

Request body:

```json
{
  "entries": [
    {
      "vital_type": "cgm",
      "value_primary": 168,
      "unit": "mg/dL",
      "captured_at": "2026-03-13T13:30:00+00:00",
      "notes": "Post lunch"
    }
  ]
}
```

### `POST /api/v1/health/vitals/import-csv`

Required CSV columns:

- `captured_at`
- `vital_type`
- `value_primary`
- `unit`

Optional columns:

- `value_secondary`
- `notes`

### `POST /api/v1/health/vitals/device-sync`

Request body:

```json
{
  "source_device": "dexcom",
  "entries": [
    {
      "vital_type": "cgm",
      "value_primary": 154,
      "unit": "mg/dL",
      "captured_at": "2026-03-13T14:00:00+00:00"
    }
  ]
}
```

### Insights semantics

The system currently reports correlation, not strong medical causation.

Expected language:

- "This spike may be associated with this meal"
- "Possible contributing factors: meal carb load, poor sleep, stress, medication timing"

Do not interpret daily/weekly insight responses as definitive medical causality.

## User Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/users/me` | Yes | Current user profile |
| `GET` | `/api/v1/users/me/usage` | Yes | Subscription and usage stats |
| `PUT` | `/api/v1/users/me` | Yes | Update profile/persona |
| `DELETE` | `/api/v1/users/me` | Yes | Delete own account |

## Package Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/packages/` | No | List packages |
| `GET` | `/api/v1/packages/{package_id}` | No | Get package |
| `POST` | `/api/v1/packages/` | Admin | Create package |
| `PUT` | `/api/v1/packages/{package_id}` | Admin | Update package |
| `DELETE` | `/api/v1/packages/{package_id}` | Admin | Soft-delete package |

## Payment Endpoints

Current payment support is placeholder-level.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/payment` | Yes | Create payment record |
| `GET` | `/api/v1/payment/history` | Yes | Payment history |

## Admin Endpoints

Admin role required.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/users` | Admin | List users |
| `GET` | `/api/v1/admin/audit-logs` | Admin | View audit logs |
| `PUT` | `/api/v1/admin/users/{user_id}/role` | Admin | Update user role |

## Legacy / Compatibility Endpoints

These still exist but should not be used for new client work.

AI compatibility endpoints:

- `GET /api/v1/ai/get-nutrition/{user_id}`
- `GET /api/v1/ai/get-report/{user_id}`
- `DELETE /api/v1/ai/delete-report/{user_id}`

Root-level legacy endpoints also still exist in `routes.py`, including older direct upload/read paths.

## Known Documentation Notes

- The public food-analysis response contract has been updated to `fooditem_details[] + nutrition`.
- In source, `GET /api/v1/ai/nutrition-data` is currently defined twice:
  - one handler for saved nutrition data
  - one handler intended for paginated history
- That path collision should be cleaned up in code; until then, treat `/api/v1/ai/nutrition-data` as an area requiring verification during frontend integration.
