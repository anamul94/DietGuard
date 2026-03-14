 Feature 1 — Nutrition Targets & BMR/TDEE Engine

  Why first: Every subsequent feature (diet plans, daily summary, adherence scoring, worsening detection) needs a number to compare against. Without targets, "you ate 2100 kcal" has no
   meaning.

  What to build:

  New model: NutritionTarget
  user_id          FK → users
  target_date      Date (effective from)
  calories_kcal    Integer
  protein_g        Numeric
  carbohydrates_g  Numeric
  fat_g            Numeric
  fiber_g          Numeric
  source           String  ("calculated" | "manual" | "plan_generated")
  calculation_basis JSONB  (BMR, TDEE, activity level used)
  is_active        Boolean
  created_at

  New service: NutritionTargetService
  - Deterministic, no LLM — pure math from PatientPersona (age from DOB, weight, height, gender)
  - Mifflin-St Jeor BMR formula
  - Activity multiplier (sedentary=1.2 by default until user sets it)
  - Condition-based adjustments: diabetes → carb cap 45% of calories; hypertension → sodium flag; kidney disease → protein restriction
  - Returns calories, protein_g, carbs_g, fat_g, fiber_g
  - Called once on first profile completion, recalculated when weight/height changes

  New API endpoints:
  - GET /api/v1/health/targets/current — returns active targets
  - POST /api/v1/health/targets — manually set/override targets
  - GET /api/v1/health/targets/adherence?date=YYYY-MM-DD — today's intake vs targets (calories/macros as % of target)

  Also add to PatientPersona: activity_level (sedentary | light | moderate | active | very_active) and timezone (string, e.g. "Asia/Kolkata") — both needed for TDEE calculation and
  end-of-day scheduling respectively.

  ---
  Feature 2 — Diet Plan Generation

  Why second: This is the core promise of the app. With targets calculated, the LLM agent has numbers to work with. With category-scoped reports working, it has accurate health
  context.

  What to build:

  Two new models: DietPlan + DietPlanMeal

  DietPlan:
  user_id
  valid_from      Date
  valid_until     Date
  generated_by    String  ("diet_plan_agent_v1")
  trigger         String  ("initial" | "report_upload" | "worsening_detected" | "manual")
  source_report_ids  JSONB  (list of report IDs that influenced this plan)
  calorie_target  Integer
  notes           Text    (LLM-generated reasoning)
  is_active       Boolean
  created_at

  DietPlanMeal:
  diet_plan_id    FK → diet_plans
  day_of_week     Integer  (0=Monday, 6=Sunday)
  meal_type       String   (breakfast | lunch | dinner | snack)
  meal_name       String
  description     Text
  foods           JSONB    (list: {name, quantity, calories, protein_g, carbs_g, fat_g})
  total_calories  Integer
  total_protein_g Numeric
  notes           Text

  Single LLM agent: diet_plan_agent

  Input context built deterministically:
  User profile: age, gender, weight, height, activity level
  Health conditions: diabetes_status, hypertension_status, kidney_stage, dyslipidemia_status
  Active medications: (from current medication schedules, with food timing)
  Lab highlights: HbA1c value, fasting glucose, LDL/HDL if available
  Food restrictions, allergies, dietary preferences
  Daily calorie/macro targets
  Location (for culturally relevant food suggestions)
  Plan duration: 7 days

  Safety guards (deterministic, before LLM call):
  - If kidney_disease_stage is not null → protein cap enforced in prompt
  - If diabetes_status == "yes" → glycemic index guidance enforced
  - If any allergy present → hard-stop list in prompt
  - If food_restrictions present → excluded foods list in prompt

  New API endpoints:
  - POST /api/v1/health/diet-plan/generate — triggers generation, returns plan
  - GET /api/v1/health/diet-plan/current — current active plan
  - GET /api/v1/health/diet-plan/history — past plans
  - GET /api/v1/health/diet-plan/today — today's meals from active plan

  Trigger logic: When a new report is uploaded and sync_structured_report_data() completes, check if any condition worsened (see Feature 3). If yes, auto-trigger plan regeneration with
   trigger="worsening_detected".

  ---
  Feature 3 — Report Trend Classification & Worsening Detection

  Why third: Needed to make the diet plan trigger meaningful, and to give users visibility into health trajectory.

  What to build:

  Extend the existing lab_trends output in get_current_health_profile() with a trend_direction field:

  def classify_trend(current, previous, canonical_name) -> str:
      delta_pct = (current - previous) / previous * 100
      # Per-lab thresholds:
      # HbA1c: +0.3 = worsening, -0.3 = improving
      # Glucose: +10 mg/dL = worsening
      # LDL: +10 mg/dL = worsening, -10 = improving
      # Creatinine: +0.2 = worsening
      # TSH: context-dependent (both high and low are bad)
      ...
      return "improving" | "stable" | "worsening"

  New service method: ReportComparisonService.evaluate_worsening(user_id, db)
  - Checks all lab trends for any "worsening" direction
  - Returns {"worsening": bool, "worsening_labs": [{"label", "delta", "current", "previous", "report_category"}]}
  - Called after each sync_structured_report_data()

  Extend sync_structured_report_data() response to include:
  {
    "worsening_detected": true,
    "worsening_labs": [{"label": "hba1c", "delta": +0.6, ...}],
    "plan_regeneration_triggered": true
  }

  ---
  Feature 4 — Daily Health Summary (End-of-Day AI Narrative)

  Why fourth: This is the daily engagement hook. Once targets and plans exist, the summary has real numbers to compare against.

  What to build:

  New model: DailySummary
  user_id
  summary_date        Date
  narrative           Text      (LLM output)
  stats_snapshot      JSONB     (all numbers used as input)
  adherence_score     Integer   (0–100, deterministic)
  alerts              JSONB     (list of alert strings)
  data_quality        String    ("sufficient" | "sparse" | "empty")
  generated_at        DateTime

  New service: DailySummaryService
  - build_context(user_id, target_date, db) — deterministic, assembles all data:
    - Meals for the day + nutrition totals
    - Active targets for the day
    - Adherence score = min(actual/target, 1.0) per macro, averaged
    - Vitals for the day (averages, min/max)
    - Correlation associations (from period insights)
    - Active conditions snapshot
    - Active medications (flag any "with_food" medications against meal times)
    - Active diet plan meals for that day of week
  - Minimum data check: skip LLM if 0 meals and 0 vitals logged
  - generate_summary(context, db) — calls DailySummaryAgent LLM

  New agent: daily_summary_agent
  - Single system prompt: warm health coach tone, not clinical
  - Output structure: day overview (2-3 sentences) + key insight (1 finding) + tomorrow's focus (1-2 actions)
  - Max 250 words

  New API endpoints:
  - POST /api/v1/health/summary/generate?date=YYYY-MM-DD — manual trigger (Phase 1 before Celery)
  - GET /api/v1/health/summary?date=YYYY-MM-DD — get stored summary
  - GET /api/v1/health/summary/recent — last 7 summaries

  ---
  Feature 5 — Background Job System (Celery)

  Why fifth: After the summary agent works manually, automate it. Also needed for device polling later.

  What to build:

  Add celery + celery[redis] to dependencies. Redis is already in the stack.

  New file: src/infrastructure/workers/celery_app.py
  - Configure Celery with Redis broker + backend
  - Beat schedule defined here

  Tasks:
  - tasks.generate_daily_summaries — runs at 21:30 UTC (adjust per timezone in Phase 2), queries all users who have data today but no summary, calls DailySummaryService for each
  - tasks.check_report_worsening — runs after each report upload (task, not scheduled)

  New Makefile target: make worker → celery -A src.infrastructure.workers.celery_app worker -l info
  New Makefile target: make beat → celery -A src.infrastructure.workers.celery_app beat -l info

  ---
  Feature 6 — Mood Check-In Routes

  Why last in Phase 2: Model already exists. Low effort, completes the data collection story before device integration.

  What to build:

  New routes in health_routes.py:
  - POST /api/v1/health/mood — create mood check-in (text input for now, audio later)
  - GET /api/v1/health/mood/history — paginated history

  Fields for Phase 1 (text-only): mood_label, energy_level (1–5), stress_level (1–5), sleep_quality (1–5), optional notes.

  Mood data already flows into get_period_insights() — it's collected and fed to the correlation graph. Just needs the write side.

  ---
  Build Order Summary

  Feature 1: Nutrition Targets + timezone/activity_level in PatientPersona
      ↓ (targets are input to plan)
  Feature 2: Diet Plan Generation
      ↓ (plan must exist before worsening can trigger re-generation)
  Feature 3: Report Trend Classification + Worsening Detection
      ↓ (targets + plan + worsening all feed the summary)
  Feature 4: Daily Summary (manual trigger first)
      ↓ (validate summary quality before automating)
  Feature 5: Celery background jobs (automate the summary)
      ↓
  Feature 6: Mood check-in routes (parallel, low effort)

  After Phase 2, the system has the full closed loop: reports influence plans → plans guide eating → meals are logged → vitals are tracked → correlation detects issues → daily summary
  explains what happened → new report confirms if it worked.
