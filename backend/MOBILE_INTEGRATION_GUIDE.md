# DietGuard Mobile Integration Guide

This guide is written for the mobile app developer. It covers every API endpoint, the
expected request/response shapes, which screen calls which endpoint, and the exact
behaviors to build against.

**Base URL:** `https://your-domain.com/api/v1`
**Auth:** All protected endpoints require `Authorization: Bearer <access_token>` header.
**Content-Type:** `application/json` (except file uploads which use `multipart/form-data`).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication](#2-authentication)
3. [Onboarding Flow](#3-onboarding-flow)
4. [Dashboard — What to Show on Home Screen](#4-dashboard)
5. [Meal Logging Flow](#5-meal-logging-flow)
6. [Vitals & Device Sync](#6-vitals--device-sync)
7. [Medical Report Upload](#7-medical-report-upload)
8. [Diet Plan](#8-diet-plan)
9. [Health Insights](#9-health-insights)
10. [Daily Summary](#10-daily-summary)
11. [User Profile Management](#11-user-profile-management)
12. [Error Reference](#12-error-reference)
13. [Phase 2 Preview — Mood Check-ins](#13-phase-2-preview--mood-check-ins)

---

## 1. Architecture Overview

```
Mobile App
│
├── Auth         → /api/v1/auth/*
├── Profile      → /api/v1/users/*
│
├── Report Upload → /api/v1/ai/upload-report
│                       ↓ (backend auto-generates diet plan on first upload)
│
├── Meal Logging → /api/v1/health/meals/*
│                  /api/v1/ai/upload-food  (image analysis)
│
├── Vitals       → /api/v1/health/vitals/*
│                  (device-sync from Health Connect / HealthKit)
│
├── Dashboard    → /api/v1/health/targets/adherence
│                  /api/v1/health/diet-plan/today
│                  /api/v1/health/meals/today-summary
│                  /api/v1/health/daily-summary
│
└── Insights     → /api/v1/health/insights/daily|weekly|monthly
```

**What the backend does automatically (no mobile action needed):**
- Generates diet plan automatically after first report upload
- Regenerates diet plan if labs worsen on a new upload
- Refreshes diet plan every Monday 06:00 in the user's local timezone
- Generates daily health summary every day at 21:00 in the user's local timezone

---

## 2. Authentication

### 2.1 Sign Up

**POST** `/auth/signup`

```json
{
  "email": "user@example.com",
  "password": "secret123",
  "full_name": "Arjun Sharma",
  "phone_number": "9876543210",
  "gender": "male",
  "date_of_birth": "1990-06-15T00:00:00",
  "height_cm": 175,
  "weight_kg": 78,
  "activity_level": "moderate",
  "current_location": "Mumbai, India",
  "timezone": "Asia/Kolkata",
  "blood_group": "O+",
  "nationality": "Indian"
}
```

**Required fields:** `email`, `password`, `full_name`
**All other fields optional** — can be updated later from profile screen.

**`activity_level` values:** `sedentary` | `light` | `moderate` | `active` | `very_active`
**`timezone`:** IANA string — e.g. `Asia/Kolkata`, `America/New_York`, `Europe/London`

**Response `201`:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "fullName": "Arjun Sharma",
    "isActive": true
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Store both tokens.** Access token expires in ~60 min. Use refresh token to get a new one.

---

### 2.2 Sign In

**POST** `/auth/signin`

```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```

**Response `200`:** Same shape as signup response above.

**Error cases:**
- `401` — wrong email or password → show "Invalid email or password"
- `403` — account disabled → show "Account inactive, contact support"

---

### 2.3 Refresh Token

**POST** `/auth/refresh-token`

```json
{
  "refresh_token": "eyJ..."
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**When to call:** Call this when any API returns `401 Unauthorized`. Replace the stored
access token and retry the original request once.

---

### 2.4 Forgot / Reset Password

**POST** `/auth/forgot-password`
```json
{ "email": "user@example.com" }
```
Always returns `200` with a generic message (security — never reveals if email exists).
Backend records the request. Wire email delivery to send the reset token.

**POST** `/auth/reset-password`
```json
{
  "token": "<token-from-email>",
  "new_password": "newpassword123"
}
```

---

### 2.5 Delete Account

**DELETE** `/auth/delete-account`
*(Requires auth header)*

HIPAA-compliant: deletes all PII, anonymises health persona data.

---

## 3. Onboarding Flow

This is the recommended screen sequence for a new user.

```
Screen 1: Register          → POST /auth/signup
Screen 2: Complete Profile  → PUT  /users/me         (height, weight, DOB, activity)
Screen 3: Upload Report     → POST /ai/upload-report  (optional but unlocks diet plan)
Screen 4: View Diet Plan    → GET  /health/diet-plan/current
```

### Screen 2 — Complete Health Profile

Show this screen if `heightCm`, `weightKg`, or `date_of_birth` are missing after signup.
Call **PUT** `/users/me` with whichever fields the user fills in.

```json
{
  "heightCm": 175,
  "weightKg": 78,
  "dateOfBirth": "1990-06-15",
  "activityLevel": "moderate",
  "timezone": "Asia/Kolkata",
  "gender": "male"
}
```

Only send fields that changed — all fields are optional in the update call.

> **Why timezone matters:** The backend uses it to schedule the daily summary at 9 PM
> the user's local time, and to refresh the diet plan Monday morning their time.
> Default is UTC if not set.

### Screen 3 — Upload Medical Report (Optional but Important)

If the user skips this, they still get a basic diet plan calculated from their BMR/TDEE.
If they upload a report, the plan becomes clinically personalised (diabetes, kidney, etc.)

**See Section 7 for the full upload flow.**

**After a successful report upload, the backend automatically:**
1. Extracts labs, medications, conditions
2. Calculates nutrition targets based on conditions
3. Generates a personalised 7-day diet plan (trigger = `"initial"`)

The mobile app should poll `GET /health/diet-plan/current` after upload
or wait for the upload response and navigate to the diet plan screen.

---

## 4. Dashboard

The home screen should aggregate data from these 4 endpoints called in parallel.

### 4.1 Today's Nutrition Target Adherence

**GET** `/health/targets/adherence?date=2026-03-14`

If `date` is omitted, defaults to today.

**Response `200`:**
```json
{
  "date": "2026-03-14",
  "target": {
    "target_id": "uuid",
    "calories_kcal": 2050,
    "protein_g": 120.0,
    "carbohydrates_g": 230.0,
    "fat_g": 68.0,
    "fiber_g": 28.0,
    "source": "calculated",
    "is_active": true
  },
  "intake": {
    "calories_kcal": 1420,
    "protein_g": 80.0,
    "carbohydrates_g": 160.0,
    "fat_g": 45.0,
    "fiber_g": 18.0
  },
  "adherence": {
    "calories_kcal": { "percent": 69.3, "status": "under" },
    "protein_g":     { "percent": 66.7, "status": "under" },
    "carbohydrates_g": { "percent": 69.6, "status": "under" },
    "fat_g":         { "percent": 66.2, "status": "under" },
    "fiber_g":       { "percent": 64.3, "status": "under" }
  },
  "generated_at": "2026-03-14T14:30:00+00:00"
}
```

**`status` values:** `met` | `over` | `under` | `no_target`

**What to show:** Ring/progress charts per nutrient. Calorie ring is the primary one.

**Error `404`:** No active nutrition target. Show "Complete your health profile to set targets."

---

### 4.2 Today's Meals Summary

**GET** `/health/meals/today-summary?target_date=2026-03-14`

```json
{
  "date": "2026-03-14",
  "meal_count": 2,
  "nutrition_totals": {
    "calories":      { "value": 1420.0, "unit": "kcal" },
    "protein":       { "value": 80.0,   "unit": "g" },
    "carbohydrates": { "value": 160.0,  "unit": "g" },
    "fat":           { "value": 45.0,   "unit": "g" },
    "fiber":         { "value": 18.0,   "unit": "g" },
    "sugar":         { "value": 22.0,   "unit": "g" }
  }
}
```

**What to show:** "2 meals logged · 1420 kcal" summary chip on home screen.

---

### 4.3 Today's Diet Plan Meals

**GET** `/health/diet-plan/today`

Returns the meals prescribed for today (filtered to current weekday automatically).

```json
[
  {
    "day_of_week": 4,
    "meal_type": "breakfast",
    "meal_name": "Oats with Banana and Almonds",
    "description": "A fibre-rich breakfast suited for blood sugar management",
    "foods": [
      { "name": "Rolled oats", "quantity": "80g", "calories": 300, "protein_g": 10, "carbs_g": 55, "fat_g": 5 },
      { "name": "Banana",      "quantity": "1 medium", "calories": 90, "protein_g": 1, "carbs_g": 23, "fat_g": 0 }
    ],
    "total_calories": 390,
    "total_protein_g": 11.0,
    "notes": null
  },
  {
    "day_of_week": 4,
    "meal_type": "lunch",
    "meal_name": "Dal Rice with Salad",
    ...
  }
]
```

**Empty list:** No active diet plan yet → show "Generate Diet Plan" CTA.

---

### 4.4 Today's Daily Summary (if available)

**GET** `/health/daily-summary?target_date=2026-03-14`

Returns `404` if no summary has been generated yet for that day (backend generates at 9 PM).

```json
{
  "summary_id": "uuid",
  "summary_date": "2026-03-14",
  "narrative": "You had a moderate day with 2 meals logged covering 69% of your calorie target. Your blood pressure reading was within range. For tomorrow, focus on hitting your protein target — try adding a boiled egg at breakfast.",
  "adherence_score": 72,
  "alerts": [],
  "data_quality": "sufficient",
  "generated_at": "2026-03-14T21:03:11+00:00"
}
```

**`data_quality`:** `sufficient` | `sparse`
**`adherence_score`:** 0–100

**What to show:** Show as a "Today's Insight" card. If `404`, hide the card (not an error).

---

## 5. Meal Logging Flow

### Option A — Photo-based (Primary Flow)

```
Step 1: User takes photo(s)
Step 2: POST /health/meals/draft-from-image   → shows editable draft
Step 3: User edits any item (name, quantity, add/remove)
          └─ POST /ai/recalculate-nutrition      → recalculates nutrition live
Step 4: POST /health/meals/confirm            → saves meal with final values
```

#### Step 2 — Draft from Image

**POST** `/health/meals/draft-from-image`
Content-Type: `multipart/form-data`
Field name: `files` (can send multiple images for the same meal)

```
files: [meal_photo.jpg, side_dish.jpg]
```

**Response `200`:**
```json
{
  "meal_title": "Indian Thali",
  "items": [
    {
      "name": "Dal Tadka",
      "quantity": "1 katori",
      "role": "main",
      "preparation": "boiled, tempered",
      "source_label": "meal_photo.jpg",
      "confidence": 0.92,
      "editable": true
    },
    {
      "name": "Basmati Rice",
      "quantity": "1 cup",
      "role": "main",
      "preparation": "steamed",
      "confidence": 0.88,
      "editable": true
    },
    {
      "name": "Papad",
      "quantity": "1 piece",
      "role": "side",
      "preparation": "roasted",
      "confidence": 0.75,
      "editable": true
    }
  ],
  "warnings": [],
  "filenames": ["meal_photo.jpg"],
  "raw_food_analysis": { ... }
}
```

**`role` values:** `main` | `side` | `condiment` | `beverage`
**`warnings`:** List of strings — e.g. `["Low confidence for item: Pickle"]`. Show as yellow chips.

**What to show:** Editable list of items. Each item should be:
- Tappable to edit name, quantity, preparation
- Deletable (remove from list before confirming)
- Show confidence as a subtle indicator (e.g. colour or icon, not a number)

---

#### Step 3 — Recalculate After User Correction

Whenever the user edits **any item** (changes name, changes quantity, adds a new item, or
removes one), call this endpoint immediately to get updated nutrition values.

**POST** `/ai/recalculate-nutrition`

```json
{
  "fooditems": [
    "1 katori rajma",
    "1 cup basmati rice",
    "1 chapati"
  ],
  "old_food_analysis": {
    "fooditem_details": [...],
    "nutrition": { ... }
  }
}
```

- **`fooditems`**: Build this list from the current state of the draft screen.
  Format each item as `"{quantity} {name}"` — e.g. `"1 katori rajma"`, `"2 chapati"`.
  If the user hasn't set a quantity, just send the name — e.g. `"rajma"`.

- **`old_food_analysis`**: Pass the `raw_food_analysis` from the draft response.
  This is optional but recommended — it gives the AI context to keep calculations
  consistent (e.g. same portion size assumptions). Pass `null` if not available.

**Response `200`:**
```json
{
  "food_analysis": {
    "fooditem_details": [
      {
        "name": "Rajma",
        "quantity": "1 katori",
        "preparation": "boiled",
        "nutrition": {
          "calories":      { "value": 210, "unit": "kcal" },
          "protein":       { "value": 13.0, "unit": "g" },
          "carbohydrates": { "value": 36.0, "unit": "g" },
          "fat":           { "value": 1.0,  "unit": "g" },
          "fiber":         { "value": 9.0,  "unit": "g" },
          "sugar":         { "value": 2.0,  "unit": "g" }
        }
      },
      {
        "name": "Basmati Rice",
        "quantity": "1 cup",
        "preparation": "steamed",
        "nutrition": {
          "calories": { "value": 205, "unit": "kcal" },
          ...
        }
      }
    ],
    "nutrition": {
      "calories":      { "value": 580, "unit": "kcal" },
      "protein":       { "value": 21.0, "unit": "g" },
      "carbohydrates": { "value": 98.0, "unit": "g" },
      "fat":           { "value": 7.0,  "unit": "g" },
      "fiber":         { "value": 14.0, "unit": "g" },
      "sugar":         { "value": 5.0,  "unit": "g" }
    }
  }
}
```

**When to call this (UX guidance):**
- Debounce by 800ms after the user stops typing a name or quantity
- Also call it when the user deletes an item or adds a new one manually
- Update the nutrition summary card at the bottom of the edit screen in real-time
- Do NOT wait until the user hits "Confirm" — they should see live totals as they edit

**Important:** The `food_analysis` returned here is what you pass to
`POST /health/meals/confirm` as the source of truth for nutrition. Store it in local
state on the review screen and update it every time this endpoint is called.

---

#### Step 4 — Confirm Meal

**POST** `/health/meals/confirm`

```json
{
  "meal_type": "lunch",
  "meal_time": "13:30",
  "meal_date": "2026-03-14",
  "items": [
    {
      "name": "Dal Tadka",
      "quantity": "1 katori",
      "role": "main",
      "preparation": "boiled, tempered"
    },
    {
      "name": "Basmati Rice",
      "quantity": "1 cup",
      "role": "main",
      "preparation": "steamed"
    }
  ],
  "source_filenames": ["meal_photo.jpg"],
  "notes": "Lunch at home"
}
```

**`meal_type`:** `breakfast` | `lunch` | `dinner` | `snack`
**`meal_time`:** 24-hour `HH:MM` format
**`meal_date`:** Cannot be in the future

**Response `200`:**
```json
{
  "meal_event_id": "uuid",
  "meal_type": "lunch",
  "meal_date": "2026-03-14",
  "meal_time": "13:30",
  "food_analysis": {
    "fooditem_details": [
      {
        "name": "Dal Tadka",
        "quantity": "1 katori",
        "calories": 180,
        "protein_g": 9.0,
        "carbohydrates_g": 24.0,
        "fat_g": 5.0,
        "fiber_g": 4.0,
        "sugar_g": 2.0
      }
    ],
    "nutrition": {
      "calories":      { "value": 540.0, "unit": "kcal" },
      "protein":       { "value": 18.0,  "unit": "g" },
      "carbohydrates": { "value": 72.0,  "unit": "g" },
      "fat":           { "value": 14.0,  "unit": "g" },
      "fiber":         { "value": 8.0,   "unit": "g" },
      "sugar":         { "value": 6.0,   "unit": "g" }
    }
  },
  "source_filenames": ["meal_photo.jpg"]
}
```

After confirming, refresh the dashboard data (adherence + today summary).

---

### Option B — Manual Text Input (No Photo)

Use this when the user types food items directly without a photo. This uses the **same
`POST /ai/recalculate-nutrition` endpoint** as the correction step in Option A.

```json
{
  "fooditems": ["1 cup dal tadka", "1 cup basmati rice", "1 chapati"],
  "old_food_analysis": null
}
```

**Response shape:** Same as Step 3 above.

Build the items list from the manual entry screen, call on every change (debounced),
then pass items to `POST /health/meals/confirm` when done.

---

### 5.1 Meal History

**GET** `/health/meals/history`

Query params (all optional):
- `start_date=2026-03-01`
- `end_date=2026-03-14`
- `page=1`
- `page_size=10`

**Response `200`:**
```json
{
  "items": [
    {
      "meal_event_id": "uuid",
      "meal_type": "lunch",
      "meal_date": "2026-03-14",
      "meal_time": "2026-03-14T08:00:00+00:00",
      "source": "confirmed_meal",
      "notes": "Lunch at home",
      "food_names": ["Dal Tadka", "Basmati Rice"],
      "items": [
        { "name": "Dal Tadka", "quantity": "1 katori", "role": "main", ... }
      ],
      "source_filenames": ["meal_photo.jpg"],
      "nutrition_totals": {
        "calories": { "value": 540.0, "unit": "kcal" },
        ...
      },
      "food_analysis": { ... }
    }
  ],
  "total_count": 28,
  "page": 1,
  "page_size": 10,
  "total_pages": 3
}
```

---

## 6. Vitals & Device Sync

### 6.1 Manual Vitals Entry

**POST** `/health/vitals`

```json
{
  "entries": [
    {
      "vital_type": "blood_pressure",
      "value_primary": 120,
      "value_secondary": 80,
      "unit": "mmHg",
      "captured_at": "2026-03-14T08:30:00+05:30",
      "notes": "Morning reading",
      "source_device": null
    },
    {
      "vital_type": "blood_glucose",
      "value_primary": 98,
      "value_secondary": null,
      "unit": "mg/dL",
      "captured_at": "2026-03-14T07:00:00+05:30",
      "notes": "Fasting"
    }
  ]
}
```

**Common `vital_type` values:**
| vital_type | value_primary | value_secondary | unit |
|---|---|---|---|
| `blood_pressure` | systolic | diastolic | `mmHg` |
| `blood_glucose` | glucose level | — | `mg/dL` or `mmol/L` |
| `heart_rate` | bpm | — | `bpm` |
| `weight` | weight | — | `kg` |
| `spo2` | oxygen % | — | `%` |
| `steps` | step count | — | `steps` |
| `sleep_hours` | hours | — | `hours` |

**Response `200`:**
```json
{
  "created_count": 2,
  "source": "manual",
  "entries": [
    {
      "vital_type": "blood_pressure",
      "value_primary": 120.0,
      "value_secondary": 80.0,
      "unit": "mmHg",
      "captured_at": "2026-03-14T03:00:00+00:00",
      "source": "manual",
      "source_device": null
    }
  ]
}
```

---

### 6.2 Device Sync — Google Health Connect / Apple HealthKit

This is the primary integration point for wearables and health platforms.

The mobile app reads data from Health Connect (Android) or HealthKit (iOS) and posts
it to the backend. No OAuth is needed on the backend side for this.

**POST** `/health/vitals/device-sync`

```json
{
  "source_device": "google_health_connect",
  "entries": [
    {
      "vital_type": "blood_glucose",
      "value_primary": 102.0,
      "value_secondary": null,
      "unit": "mg/dL",
      "captured_at": "2026-03-14T06:00:00+05:30",
      "metadata": { "record_id": "abc123", "data_origin": "com.dexcom.g7" }
    },
    {
      "vital_type": "heart_rate",
      "value_primary": 72.0,
      "value_secondary": null,
      "unit": "bpm",
      "captured_at": "2026-03-14T07:15:00+05:30"
    }
  ]
}
```

**`source_device` examples:** `google_health_connect` | `apple_healthkit` | `fitbit` | `dexcom_g7`

**Recommended sync strategy on mobile:**
- Sync on app foreground (once per session)
- Sync on demand from settings
- Store last-synced timestamp locally, only send new records

---

### 6.3 CSV Vitals Import

For users who export data from their CGM or fitness device as CSV.

**POST** `/health/vitals/import-csv`
Content-Type: `multipart/form-data`
Field: `file` (`.csv` only)

**CSV format:**
```
vital_type,value_primary,value_secondary,unit,captured_at,notes
blood_glucose,98,,mg/dL,2026-03-14T07:00:00,Fasting
blood_pressure,120,80,mmHg,2026-03-14T08:30:00,Morning
```

---

## 7. Medical Report Upload

This is the most important onboarding action. A lab report or prescription PDF/image
triggers clinical personalisation of the entire platform.

**POST** `/ai/upload-report`
Content-Type: `multipart/form-data`
Field: `files` (PDF or JPG/PNG, can send multiple files in one request)

```
files: [blood_test_report.pdf, prescription.jpg]
```

**What happens on the backend (automatically, in order):**
1. Each file is parsed by the AI report agent
2. Reports are grouped by category (metabolic, thyroid, renal, etc.)
3. For each category: labs, medications, conditions, entities are stored
4. Nutrition targets are recalculated based on detected conditions
5. If no diet plan exists → a personalised 7-day plan is generated automatically
6. If labs show worsening compared to previous upload → plan is regenerated

**Response `200`:**
```json
{
  "files_processed": 2,
  "filenames": ["blood_test_report.pdf", "prescription.jpg"],
  "version": 3,
  "uploaded_at": "2026-03-14T10:22:00+00:00",
  "ehr_data": { ... },
  "structured_health_profiles": [
    {
      "report_id": "uuid",
      "report_category": "metabolic",
      "version": 3,
      "summary": "HbA1c elevated at 7.8%. Metformin prescribed. Low GI diet recommended.",
      "worsening_detected": false,
      "worsening_labs": [],
      "plan_regeneration_triggered": true
    }
  ]
}
```

**After upload, navigate the user to:**
- `GET /health/diet-plan/current` → show their new personalised plan
- `GET /health/profile/current` → show their health profile summary

---

### 7.1 Get Structured Health Profile

**GET** `/health/profile/current`

Returns the merged health profile from all uploaded reports.

```json
{
  "report": {
    "report_id": "uuid",
    "version": 3,
    "report_date": "2026-03-10",
    "summary": "HbA1c elevated. Metformin prescribed.",
    "report_category": "metabolic"
  },
  "current_reports": [
    { "report_category": "metabolic", "version": 3, ... },
    { "report_category": "thyroid",   "version": 1, ... }
  ],
  "snapshot": {
    "diabetes_status": "yes",
    "hypertension_status": "no",
    "kidney_disease_stage": null,
    "dyslipidemia_status": "unknown",
    "food_restrictions": ["refined sugar", "white rice"],
    "allergies": [],
    "dietary_preferences": ["vegetarian"],
    "doctor_advice": ["Limit carbs to 45% of calories"],
    "extra_conditions": []
  },
  "labs": [
    {
      "report_category": "metabolic",
      "test_name": "HbA1c",
      "canonical_name": "hba1c",
      "value_text": "7.8%",
      "value_numeric": 7.8,
      "unit": "%",
      "reference_range": "4.0-5.6",
      "interpretation": "High",
      "abnormal_flag": "H",
      "lab_date": "2026-03-10"
    }
  ],
  "medications": [
    {
      "medication_name": "Metformin",
      "dosage": "500mg",
      "schedule": "Twice daily",
      "with_food": true,
      "timing_notes": "After meals"
    }
  ],
  "lab_trends": [
    {
      "label": "hba1c",
      "current_value": 7.8,
      "previous_value": 7.2,
      "delta": 0.6,
      "unit": "%",
      "trend_direction": "worsening",
      "current_date": "2026-03-10",
      "previous_date": "2025-12-01"
    }
  ],
  "active_categories": ["metabolic"],
  "health_context_summary": "Patient has Type 2 Diabetes (HbA1c 7.8%). On Metformin 500mg BD. Follow low GI diet."
}
```

**`trend_direction` values:** `improving` | `stable` | `worsening`
**What to show for lab_trends:** A small trend arrow (↑ red, ↓ green, → grey) next to each lab value.

---

## 8. Diet Plan

### 8.1 Get Current Plan

**GET** `/health/diet-plan/current`

```json
{
  "plan_id": "uuid",
  "valid_from": "2026-03-14",
  "valid_until": "2026-03-20",
  "generated_by": "diet_plan_agent_v1",
  "trigger": "initial",
  "calorie_target": 1850,
  "notes": "Plan designed for a diabetic patient. All meals are low GI. Protein is within renal-safe limits.",
  "is_active": true,
  "meals": [
    {
      "day_of_week": 0,
      "meal_type": "breakfast",
      "meal_name": "Vegetable Oats Upma",
      "description": "High fibre, low GI breakfast",
      "foods": [
        { "name": "Rolled oats", "quantity": "60g", "calories": 230, "protein_g": 8, "carbs_g": 40, "fat_g": 4 },
        { "name": "Mixed vegetables", "quantity": "100g", "calories": 40, "protein_g": 2, "carbs_g": 8, "fat_g": 0 }
      ],
      "total_calories": 270,
      "total_protein_g": 10.0,
      "notes": "Use minimal oil"
    }
  ]
}
```

**`day_of_week`:** `0` = Monday, `6` = Sunday
**`trigger` values:** `initial` | `manual` | `worsening_detected` | `scheduled_weekly` | `plan_expired`

**Error `404`:** No active plan. Show "Generate Diet Plan" button.

---

### 8.2 Today's Meals (Diet Plan)

**GET** `/health/diet-plan/today`

Returns only the meals for today's weekday from the current plan. Empty list if no plan.

---

### 8.3 Generate Plan Manually

**POST** `/health/diet-plan/generate`

No request body needed.

Use this if the user taps "Regenerate My Plan" in the app.

```json
{}
```

Returns the new `DietPlanResponse`. Error `400` if no health profile / nutrition target exists.

---

### 8.4 Plan History

**GET** `/health/diet-plan/history`

Returns all past plans (most recent first). Useful for a "History" screen.

---

## 9. Health Insights

These power the weekly/monthly review screens.

### 9.1 Daily Insights

**GET** `/health/insights/daily?target_date=2026-03-14`

### 9.2 Weekly Insights

**GET** `/health/insights/weekly?end_date=2026-03-14`

### 9.3 Monthly Insights

**GET** `/health/insights/monthly?end_date=2026-03-14`

All three return the same shape:

```json
{
  "period_start": "2026-03-08T00:00:00+00:00",
  "period_end":   "2026-03-14T23:59:59+00:00",
  "meal_count": 18,
  "vital_count": 9,
  "mood_checkin_count": 0,
  "nutrition_totals": {
    "calories": 12600,
    "protein_g": 560.0,
    "carbohydrates_g": 1680.0,
    "fat_g": 420.0
  },
  "vital_overview": [
    {
      "vital_type": "blood_glucose",
      "count": 7,
      "average_primary": 104.3,
      "unit": "mg/dL"
    }
  ],
  "associations": [
    {
      "meal_id": "uuid",
      "vital_id": "uuid",
      "meal_time": "...",
      "vital_time": "...",
      "vital_type": "blood_glucose",
      "confidence_tier": "medium",
      "association_label": "Post-meal glucose spike",
      "explanation": "Blood glucose rose by 28 mg/dL within 90 minutes of a high-carb meal.",
      "possible_factors": ["High rice portion", "Low fibre in meal"],
      "evidence": { ... }
    }
  ],
  "narrative": "This week you logged 18 meals with an average of 1800 kcal/day. Your blood glucose was consistently below 110 mg/dL, showing good meal control.",
  "possible_factors": ["Consistent meal timing", "Low-GI food choices"]
}
```

**What to show on Insights screen:**
- Bar chart for daily calories over the period
- Vital averages (glucose, BP) with trend vs previous period
- Association cards — these are AI-generated meal-vital correlations
- Narrative paragraph as a summary card

---

## 10. Daily Summary

The backend generates this automatically every day at **21:00 in the user's local timezone**.
The mobile app just fetches and displays it.

### 10.1 Get Summary for a Date

**GET** `/health/daily-summary?target_date=2026-03-14`

Returns `404` if not yet generated (it's before 9 PM, or no meals/vitals were logged).

### 10.2 Generate On Demand

**POST** `/health/daily-summary/generate`

```json
{
  "summary_date": "2026-03-14"
}
```

Returns `400` if there are no meals or vitals for that date.
Returns existing summary if one already exists (idempotent).

### 10.3 Recent Summaries

**GET** `/health/daily-summary/recent?limit=7`

Returns last N summaries (default 7, max 30). Use this for a "Past Week" review screen.

```json
[
  {
    "summary_id": "uuid",
    "summary_date": "2026-03-14",
    "narrative": "Good day overall. You met 89% of your calorie target...",
    "adherence_score": 89,
    "alerts": [],
    "data_quality": "sufficient",
    "generated_at": "2026-03-14T21:03:11+00:00"
  }
]
```

---

## 11. User Profile Management

### 11.1 Get Profile

**GET** `/users/me`

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "fullName": "Arjun Sharma",
  "phoneNumber": "9876543210",
  "age": 35,
  "gender": "male",
  "bloodGroup": "O+",
  "heightCm": 175.0,
  "weightKg": 78.0,
  "currentLocation": "Mumbai, India",
  "activityLevel": "moderate",
  "timezone": "Asia/Kolkata",
  "dateOfBirth": "1990-06-15",
  "isActive": true,
  "createdAt": "2026-01-01T10:00:00+00:00"
}
```

### 11.2 Update Profile

**PUT** `/users/me`

Send only the fields to change:

```json
{
  "weightKg": 76.5,
  "activityLevel": "active",
  "timezone": "Asia/Kolkata"
}
```

> **Important:** When `weightKg`, `heightCm`, `dateOfBirth`, `gender`, or `activityLevel`
> changes, the backend **automatically recalculates nutrition targets**. No extra call needed.

### 11.3 Get Usage Stats

**GET** `/users/me/usage`

```json
{
  "plan_type": "free",
  "status": "active",
  "uploads_today": 1,
  "remaining_uploads": 1,
  "max_daily_uploads": 2
}
```

Show this on the profile or settings screen so users know their limits.

---

## 12. Error Reference

| Status | When | What to show |
|--------|------|--------------|
| `400` | Validation error (e.g. future date) | Show `detail` message from response body |
| `401` | Token expired or invalid | Refresh token → retry once → if still 401, redirect to login |
| `403` | Account inactive or insufficient role | "Account inactive. Contact support." |
| `404` | Resource doesn't exist yet | Show appropriate empty state (not an error in UX) |
| `422` | Wrong file type or format | Show `detail` message from response body |
| `429` | Daily upload limit reached | "You've reached today's upload limit. Upgrade to continue." |
| `500` | Server error | "Something went wrong. Please try again." |

**Error response body always has:**
```json
{ "detail": "Human-readable message here" }
```

**Token expiry handling (recommended):**
```
Request → 401
  → POST /auth/refresh-token with refresh_token
  → Success: update access_token, retry original request
  → Failure (refresh also 401): clear tokens, redirect to login screen
```

---

## 13. Phase 2 Preview — Mood Check-ins

This feature is available.

**POST** `/health/mood/checkin` (multipart/form-data)
- Fields:
  - `audio`: required file (`.m4a/.mp4/.mp3/.wav`)
  - `consent`: required boolean, must be `true`
  - `captured_at`: optional ISO datetime (if omitted, server uses current UTC time)
  - `user_local_time`: optional ISO datetime with offset from the device (recommended for best time-of-day accuracy)
- Response includes:
  - `mood_checkin_id`
  - `user_id`
  - `session_id`
  - `transcript`
  - `captured_at` (UTC)
  - `analyzed_at` (UTC)
  - `user_local_time`
  - `time_of_day` (`morning|afternoon|evening|night`)
  - `day_of_week`
  - `primary_emotion` (one word)
  - `secondary_emotions` (list)
  - `stress_level` (0-100)
  - `key_stress_indicators` (list)
  - `urgency_level` (`low|medium|high`)
  - `summary` (one sentence)

**GET** `/health/mood/history`
- Returns recent mood check-ins (paginated) including transcript and extracted fields.

**Integration note for mobile:** Plan for a daily check-in prompt, ideally at night before
the daily summary is generated (around 8:30 PM). The daily summary and insights can
incorporate mood data once check-ins exist.

---

## Quick Reference — All Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/auth/signup` | No | Register |
| POST | `/auth/signin` | No | Login |
| POST | `/auth/refresh-token` | No | Refresh access token |
| POST | `/auth/forgot-password` | No | Request password reset |
| POST | `/auth/reset-password` | No | Reset password |
| DELETE | `/auth/delete-account` | Yes | Delete account |
| GET | `/users/me` | Yes | Get profile |
| PUT | `/users/me` | Yes | Update profile |
| GET | `/users/me/usage` | Yes | Get upload usage |
| POST | `/ai/upload-report` | Yes | Upload medical report |
| GET | `/ai/report-data` | Yes | Get structured health profile |
| DELETE | `/ai/report-data` | Yes | Delete report history |
| POST | `/ai/upload-food` | Yes | Analyse food images |
| POST | `/ai/scan-ingredients` | Yes | Scan food packaging |
| POST | `/ai/nutrition-advice` | Yes | Get AI nutrition advice |
| POST | `/ai/recalculate-nutrition` | Yes | Calculate nutrition for text items |
| GET | `/ai/nutrition-data` | Yes | Paginated meal history |
| GET | `/ai/nutrition-data/today` | Yes | Today's meal history |
| GET | `/health/profile/current` | Yes | Structured health profile |
| GET | `/health/targets/current` | Yes | Current nutrition target |
| POST | `/health/targets` | Yes | Set manual nutrition target |
| GET | `/health/targets/adherence` | Yes | Today's adherence vs target |
| POST | `/health/meals/draft-from-image` | Yes | Get meal draft from photo |
| POST | `/health/meals/confirm` | Yes | Confirm and save meal |
| GET | `/health/meals/today-summary` | Yes | Today's meal nutrition totals |
| GET | `/health/meals/history` | Yes | Paginated meal history |
| POST | `/health/vitals` | Yes | Log vitals manually |
| POST | `/health/vitals/import-csv` | Yes | Import vitals from CSV |
| POST | `/health/vitals/device-sync` | Yes | Sync from Health Connect/HealthKit |
| GET | `/health/insights/daily` | Yes | Daily period insights |
| GET | `/health/insights/weekly` | Yes | Weekly period insights |
| GET | `/health/insights/monthly` | Yes | Monthly period insights |
| POST | `/health/diet-plan/generate` | Yes | Generate new diet plan |
| GET | `/health/diet-plan/current` | Yes | Get active diet plan |
| GET | `/health/diet-plan/history` | Yes | All past plans |
| GET | `/health/diet-plan/today` | Yes | Today's meals from plan |
| POST | `/health/daily-summary/generate` | Yes | Generate daily summary |
| GET | `/health/daily-summary` | Yes | Get summary for a date |
| GET | `/health/daily-summary/recent` | Yes | Last N daily summaries |
| POST | `/health/mood/checkin` | Yes | Audio mood check-in (transcribe + mood/stress analysis) |
| GET | `/health/mood/history` | Yes | Paginated mood check-in history |
