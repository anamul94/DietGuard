# DietGuard AI

**AI-powered nutrition and longitudinal health platform.** DietGuard analyses medical reports and food photos with multimodal LLMs, converts the results into a structured personal health record, and turns that record into personalised diet plans, recipes, meal schedules, and daily clinical summaries.

Built as a FastAPI backend (v2.0.0) with a Socket.IO real-time channel, PostgreSQL for structured clinical data, and a pluggable LLM layer (AWS Bedrock by default, any LangChain provider supported).

---

## Table of Contents

- [What DietGuard Does](#what-dietguard-does)
- [Feature Overview](#feature-overview)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [AI Agents](#ai-agents)
- [LLM Provider Configuration](#llm-provider-configuration)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Security & Privacy](#security--privacy)
- [Subscription Model](#subscription-model)
- [Background Jobs](#background-jobs)
- [Real-Time Events](#real-time-events)
- [Admin Dashboard](#admin-dashboard)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Documentation](#documentation)
- [License](#license)

---

## What DietGuard Does

DietGuard started as a "photo in, nutrition out" analyser and grew into a longitudinal health platform. The core loop is:

1. **Ingest** — a medical report, a food photo, a packaging label, a diet chart from a doctor, a voice check-in, or a batch of vitals from a wearable.
2. **Parse** — a vision/document LLM extracts structured data (labs, conditions, medications, food items, ingredients, diet restrictions).
3. **Normalise** — the raw output is persisted into normalised clinical tables (`lab_results`, `medical_condition_snapshots`, `medication_schedules`, `meal_events`, `meal_items`, `vital_events`, `mood_checkins`).
4. **Reason** — downstream agents and a deterministic correlation engine turn that timeline into a diet plan, recipes, a weekly schedule, insights, and an end-of-day summary.

The distinctive part is step 3: DietGuard does not treat each upload as an isolated event. Every meal, vital, mood entry, and report version lands on one timeline that later generations read from.

---

## Feature Overview

### Clinical & AI Analysis

| Feature | Description |
| --- | --- |
| 🏥 **Medical Report Analysis** | Upload PDFs and images of lab reports, prescriptions, discharge summaries, or radiology reports. The `report_agent` extracts a dynamic structure (`documentType`, `sections[]`, `entities[]`, `unmappedEntities[]`) rather than a fixed schema, so unfamiliar report formats still parse. |
| 🔗 **Report Merging & Versioning** | Uploading a newer report merges it with the previous one into a FHIR-inspired `DiagnosticReport`. Each test carries a `history[]` of prior values, so trends survive across uploads. Reports are versioned and scoped per `report_category`. |
| 🩺 **Condition Snapshots** | Current status of diabetes, hypertension, kidney disease stage, dyslipidemia, allergies, food restrictions, and doctor advice is maintained as a point-in-time snapshot per report category. |
| 💊 **Medication Extraction** | Prescribed medications are captured with dosage, schedule, timing notes, and with-food flags, and feed into the diet plan and daily summary. |
| 🍎 **Food Image Analysis** | Multi-image meal photos are recognised by the `food_agent` into per-item detail (`fooditem_details[]`) with per-item and total macros. Non-food images are rejected explicitly rather than hallucinated. |
| 🔬 **Ingredient / Packaging Scan** | The `ingredient_scanner_agent` reads food packaging labels and returns an ingredient breakdown, red/amber/green ingredient ratings, allergens, age restrictions, dietary compatibility, and a **Singapore NutriGrade (A–D)** score. |
| 🧮 **Nutrition Calculation** | `nutrition_calculator_agent` computes macros from plain text item descriptions (e.g. `"150g cooked brown rice"`) against USDA FoodData Central / NCCDB reference servings. |
| 🔁 **Nutrition Recalculation** | When a user corrects AI-identified foods, the `nutrition_recalculator_agent` recomputes all values from the corrected items. |
| 🧑‍⚕️ **Nutritionist Advice** | The `nutritionist_agent` produces a personalised, free-text markdown assessment combining the meal, the medical report, and the user's persona. |
| 🗣️ **Audio Mood Check-ins** | Record a voice journal entry. It is transcribed with AWS Transcribe, then analysed for primary/secondary emotion, stress level (0–100), key stress indicators, and urgency. Audio is deleted from S3 immediately after transcription. |

### Health Timeline & Tracking

| Feature | Description |
| --- | --- |
| 🕰️ **Longitudinal Timeline** | Meals, vitals, mood check-ins, and reports share one time-indexed timeline with per-event versioning. |
| 🍽️ **Draft → Confirm Meal Flow** | A photo produces a *draft* the user can correct before anything is persisted. Only confirmed meals enter the timeline. |
| ❤️ **Vitals Ingestion** | Vitals arrive three ways: manual entry, CSV import, and generic device sync (Health Connect / HealthKit payload shape). Device sync is idempotent via deterministic UUIDv5 keys, so re-syncing never duplicates rows. |
| 🎯 **Nutrition Targets** | A **deterministic, LLM-free** engine computes daily targets: Mifflin-St Jeor BMR → TDEE → calories (floor 1200), then protein/fat/carbohydrate/fiber splits that adapt to clinical context (kidney stage lowers protein; diabetes caps carbs at 45% of calories). |
| 📈 **Adherence Tracking** | Per-metric adherence with `under` / `on_track` / `over` status against the day's target. |
| 🔗 **Health Correlation Engine** | A deterministic, LLM-free LangGraph workflow links meals to vitals inside clinically meaningful post-meal windows (glucose 30–180 min, BP 30–240 min, heart rate 15–120 min), compares against a rolling baseline, and reports **associations, never causation**. |
| 🌤️ **Daily & Weekly Insights** | Daily, weekly, and monthly period insights built on the correlation engine, with `possible_factors` such as meal carb load, current diabetes context, medication timing, stress, and poor sleep. |
| 🗓️ **Diet Plan Generation** | A 7-day, condition-aware, culturally-aware plan (Muslim, Hindu/Indian, Jewish, vegetarian, vegan rules encoded) generated from the health snapshot, medications, and calorie targets. |
| 📝 **Daily Summaries** | An end-of-day clinical narrative plus alerts (BP > 140/90, glucose > 180 mg/dL, SpO₂ < 95%) assembled from meals, vitals, and condition snapshots. |

### Recipes & Meal Planning

| Feature | Description |
| --- | --- |
| 📄 **Diet Chart Ingestion** | Upload a doctor's diet chart, prescription, or nutritionist plan (image/PDF). The `diet_chart_agent` extracts *avoid*, *limit*, and *allowed* foods plus nutrition targets and meal plan targets, with an extraction confidence rating. |
| ✍️ **Manual Diet Profiles** | Enter restrictions and preferences by hand instead of uploading a chart. |
| 🍽️ **Personalised Recipes** | The `recipe_suggestion_agent` generates single recipes matched to diet restrictions, cuisine preference, diet type, allergies, disliked ingredients, cooking-time band, and per-meal calorie split. |
| 📅 **Weekly Meal Schedules** | A full 7-day schedule with breakfast/lunch/dinner/snack recipes, sliced from the agent's weekly output. |
| ❤️ **Favourites & Tracking** | Toggle favourites, and track a recipe as `cooked` / `ate` / `skipped` / `replaced`. Cooking or eating a recipe writes a real `meal_events` row into the meal tracker. |
| 🛡️ **Safety Filters** | Recipes never contain `avoid_foods`, respect `limit_foods` and allergies, and carry per-condition guidance for diabetes, hypertension, kidney disease, heart disease, and pregnancy. |

### Platform

| Feature | Description |
| --- | --- |
| 🔐 **JWT Authentication** | Access + refresh tokens with typed claims (`access` / `refresh`), refresh-token exchange, and Argon2id password hashing. |
| 🛡️ **HIPAA-Aligned Data Handling** | Patient PII is AES-256-GCM encrypted at rest, every PHI read/write is audit-logged, and account deletion anonymises rather than orphans records. |
| 👥 **Role-Based Access** | `roles` / `user_roles` tables with `require_role` / `require_user` / `require_admin` dependencies. |
| 💳 **Subscriptions & Packages** | Free tier with daily quotas, paid tier, admin-assigned packages, trial tracking, and automatic downgrade on expiry. |
| 📊 **Audit Logging** | General security audit trail plus a dedicated HIPAA PHI access/modification trail. |
| 🔍 **LLM Token Accounting** | Per-agent token usage is tracked per request and exposed through admin analytics (daily, per-model, top consumers). |
| 🧩 **Pluggable LLM Providers** | Per-agent provider and model overrides — switch one agent to a local Ollama model without touching the rest. |
| 📡 **Socket.IO Channel** | Real-time event stream for long-running analysis completions. |
| 🖥️ **Streamlit Admin Dashboard** | A standalone admin UI for users, roles, packages, and audit logs. |
| 🐳 **Docker & AWS Ready** | Docker Compose for local runs, plus CodeBuild/CodeDeploy and CloudFormation templates for AWS. |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Clients                                     │
│  Mobile App  ·  Web  ·  Streamlit Admin  ·  Socket.IO Clients      │
└───────────────┬────────────────────────────┬───────────────────────┘
                │ HTTPS / Socket.IO          │
┌───────────────▼────────────────────────────▼───────────────────────┐
│                    FastAPI Application (v2.0.0)                     │
│  ┌──────────┬──────────┬───────────┬──────────┬──────────────────┐  │
│  │  Auth    │   AI     │  Health   │ Recipes  │  Admin / Users   │  │
│  │  Routes  │  Routes  │  Routes   │  Routes  │  Packages / Pay  │  │
│  └────┬─────┴────┬─────┴─────┬─────┴────┬────┴────────┬─────────┘  │
│       │          │           │          │             │            │
│  ┌────▼──────────▼───────────▼──────────▼─────────────▼─────────┐  │
│  │              Application Services (13 services)                │  │
│  │ Auth · Audit · HIPAA Audit · Patient · Health Timeline        │  │
│  │ Diet Plan · Daily Summary · Nutrition Target · Recipe         │  │
│  │ Report Comparison · Subscription · Token Usage                 │  │
│  └────┬──────────────────────────────┬───────────────────────────┘  │
│       │                              │                             │
│  ┌────▼─────────────────────┐  ┌─────▼────────────────────────────┐  │
│  │   Infrastructure        │  │      AI Agent Layer (14)        │  │
│  │  · LLM Factory          │  │  Vision: food, ingredients,     │  │
│  │  · JWT / Password       │  │           reports, diet charts  │  │
│  │  · AES-256-GCM Crypto   │  │  Text:   nutrition calc, plan,  │  │
│  │  · Image Preprocessing  │  │           summary, recipes,     │  │
│  │  · AWS Transcribe       │  │           mood, merge          │  │
│  │  · Scheduler (APSched)  │  └────────────────────────────────┘  │
│  │  · LangGraph Correlation│                                     │
│  │  · Socket.IO / RabbitMQ │  ┌────────────────────────────────┐  │
│  └────┬────────────────────┘  │   LLM Providers (pluggable)    │  │
│       │                       │  AWS Bedrock · Ollama · Any    │  │
│       │                       │  LangChain chat model          │  │
└───────▼───────────────────────┴────────────────────────────────┘
                │
       ┌────────▼─────────┐    ┌──────────────┐    ┌──────────────┐
       │   PostgreSQL 15  │    │     Redis    │    │  AWS S3      │
       │  30+ tables      │    │  blob cache  │    │  (audio)     │
       └──────────────────┘    └──────────────┘    └──────────────┘
```

### Tech Stack

| Layer | Technology |
| --- | --- |
| API Framework | FastAPI 0.117+ (Python 3.11+), served with Uvicorn |
| Real-time | python-socketio 5.10 (ASGI) |
| ORM / Migrations | SQLAlchemy 2.0 (async) + Alembic, asyncpg driver |
| Database | PostgreSQL 15 (Alpine) |
| Cache | Redis (legacy blob cache: reports 12 h TTL, nutrition 24 h TTL) |
| AI Framework | LangChain 0.3+ (`init_chat_model`), LangGraph 0.6+ (correlation workflow) |
| LLM — default | AWS Bedrock (Claude 3.7 Sonnet via inference profile) |
| LLM — alternative | Ollama (local `glm-4.7-flash`) or any LangChain chat model |
| Speech-to-text | AWS Transcribe (batch) for mood check-ins |
| Validation | Pydantic v2 + pydantic-settings |
| Security | python-jose (JWT), Argon2id, cryptography (AES-256-GCM) |
| Scheduling | APScheduler (AsyncIOScheduler, cron jobs) |
| Admin UI | Streamlit + pandas + requests |
| Deployment | Docker Compose, AWS CodeBuild / CodeDeploy, CloudFormation |

---

## Repository Layout

```
DietGuard/
├── backend/                     # FastAPI application
│   ├── main.py                  # Entry point (exposes the Socket.IO ASGI app)
│   ├── alembic/                 # 20 migrations, 1 head (1ea7e4b8e1b9)
│   ├── scripts/                 # Seeding, key generation, service scripts
│   ├── infra/cloudformation/    # AWS infra templates
│   ├── docs/                    # Backend-specific docs
│   ├── test/                    # pytest suite
│   └── src/
│       ├── presentation/        # API routers + Pydantic schemas
│       ├── application/         # Service layer (13 services)
│       ├── domain/              # Entities, enums, units
│       └── infrastructure/      # Agents, graphs, DB, auth, security, utils
├── admin_frontend/              # Streamlit admin dashboard
├── apk/                         # Pre-built Android client (nutriApp.apk)
├── docs/                        # API reference, feature guides, status reports
├── index.html                   # Socket.IO event-stream viewer
├── ingredient-analysis.html     # Ingredient analysis report template
├── docker-compose.yml           # Backend + PostgreSQL
├── Makefile                     # Top-level task runner
└── DOCKER_README.md             # Docker-specific instructions
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An AWS account with Bedrock model access (for the default LLM provider), **or**
- [Ollama](https://ollama.com) running locally (for a fully local setup)

### 1. Clone and configure

```bash
git clone <repository-url>
cd DietGuard
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set at minimum:

```bash
# Required — generate a strong key
JWT_SECRET_KEY=<min-32-char-random-string>

# Required — generate with: cd backend && uv run python scripts/generate_encryption_key.py
ENCRYPTION_KEY=<base64-encoded-32-byte-key>

# Required for the default LLM provider
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_REGION=ap-south-1
```

See [Configuration](#configuration) for the full list.

### 2. Start the stack

```bash
docker compose up -d
```

The backend container waits for PostgreSQL, runs `alembic upgrade head` automatically, then starts Uvicorn with hot reload.

### 3. Seed reference data

```bash
make seed        # roles + subscription packages
```

### 4. Verify

```bash
curl http://localhost:8011/health
```

Expected: `{"status":"healthy", "service":"dietguard-backend", "version":"2.0.0", "checks":{"database":"healthy"}}`

### 5. Open the docs

| Service | URL |
| --- | --- |
| Swagger UI | http://localhost:8011/docs |
| ReDoc | http://localhost:8011/redoc |
| Health check | http://localhost:8011/health |
| PostgreSQL | `localhost:5437` (container `5432`) |
| Socket.IO event viewer | open `index.html` in a browser |

### Useful Make Targets

```bash
make help          # list all targets
make up            # start services
make down          # stop services
make build         # rebuild and start
make logs          # tail all logs
make migrate       # run alembic upgrade head
make seed          # seed roles + packages
make setup         # build + migrate + seed
make status        # container status
make health        # API health check
make clean         # stop and remove containers + volumes (destructive)
```

The backend directory has a richer set of targets (`make -C backend help`): `test`, `test-coverage`, `lint`, `format`, `create-migration`, `migration-history`, `reset-db`, `backup-db`, `restore-db`, `generate-key`, `check-env`, and more.

### Manual (non-Docker) Setup

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run python scripts/seed_roles.py
uv run python scripts/seed_packages.py
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# PostgreSQL (if not already running)
docker run -d -p 5432:5432 --name dietguard-postgres \
  -e POSTGRES_DB=dietguard -e POSTGRES_USER=dietguard \
  -e POSTGRES_PASSWORD=dietguard123 postgres:15-alpine
```

---

## Configuration

All backend configuration lives in `backend/.env` (see `backend/.env.example` for the annotated template).

### Database

```bash
DATABASE_URL=postgresql+asyncpg://dietguard:dietguard123@localhost:5432/dietguard
POSTGRES_USER=dietguard
POSTGRES_PASSWORD=dietguard123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dietguard
```

### Authentication & Security

```bash
JWT_SECRET_KEY=<min-32-char-random-string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1
ADMIN_KEY=<admin-api-key>          # NOT present in .env.example — set it yourself
ENCRYPTION_KEY=<base64-32-byte-key> # generate with scripts/generate_encryption_key.py
```

### Subscription Limits

```bash
FREE_TIER_DAILY_UPLOAD_LIMIT=2
FREE_TIER_DAILY_NUTRITION_LIMIT=2
```

### AWS

```bash
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_SESSION_TOKEN=<token>          # required for temporary (ASIA…) credentials
AWS_PROFILE=<profile>
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=<explicit-model-or-inference-profile-id>
INFERENCE_PROFILE_ID=global.anthropic.claude-sonnet-4-6
```

> **Note:** `BEDROCK_MODEL_ID` takes precedence over `INFERENCE_PROFILE_ID`. The `.env.example` ships a placeholder value for it — **replace or remove it**, or that literal string becomes your model id.

### AWS Transcribe (Mood Check-ins)

```bash
TRANSCRIBE_S3_BUCKET=<private-bucket>
TRANSCRIBE_S3_PREFIX=mood-checkins/
TRANSCRIBE_LANGUAGE_CODE=en-US
TRANSCRIBE_TIMEOUT_SECONDS=180
TRANSCRIBE_POLL_INTERVAL_SECONDS=2
MAX_MOOD_AUDIO_MB=12
```

The S3 object is deleted in a `finally` block immediately after the transcription attempt. The bucket should also have a lifecycle rule as a backstop — see `backend/infra/cloudformation/mood-checkins-s3.yml`.

### Redis (legacy blob cache)

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=myredissecret
```

### Application

```bash
APP_NAME=DietGuard
DEBUG=True
LOG_LEVEL=INFO
```

---

## AI Agents

14 agents live in `backend/src/infrastructure/agents/`. Each is a single-shot, stateless prompt→response call — no tools, no conversation memory, no checkpointer. Context is passed explicitly in each prompt.

| Agent | Modality | Output | Purpose |
| --- | --- | --- | --- |
| `food_agent` | Vision (multi-image) | `FoodAnalysis` | Identify foods in a meal photo; per-item + total nutrition. Explicitly rejects non-food images. |
| `ingredient_scanner_agent` | Vision | `IngredientAnalysis` | Read packaging: ingredient list, ratings, allergens, age limits, **NutriGrade A–D**. |
| `report_agent` | Vision + PDF | JSON (prompt-contract) | Extract medical report structure: `documentType`, `sections[]`, `entities[]`, `unmappedEntities[]`. |
| `report_merge_agent` | Text | JSON | Merge old + new reports into a FHIR-inspired `DiagnosticReport` with per-test `history[]`. |
| `diet_chart_agent` | Vision + PDF + Text | `DietChartExtraction` | Parse a doctor's diet chart into avoid/limit/allowed foods, targets, and meal plan. Returns an extraction confidence (high/medium/low/**none**). |
| `nutrition_calculator_agent` | Text | `NutritionCalculation` | Compute macros from plain-text food items (USDA FoodData Central / NCCDB reference servings). |
| `nutrition_recalculator_agent` | Text | `NutritionRecalculation` | Recompute macros after a user corrects AI-identified foods. |
| `nutritionist_agent` | Text | Markdown | Personalised meal assessment and advice (~200 words, 5 fixed sections). |
| `summary_agent` | Text | Plain string | TTS-ready spoken summary of a nutrition report. |
| `daily_summary_agent` | Text | `DailySummaryResult` | End-of-day clinical narrative + alerts from meals, vitals, and conditions. |
| `diet_plan_agent` | Text | `DietPlanGenerationResult` | 7-day condition-aware, culturally-aware plan (Mon–Sun). |
| `recipe_suggestion_agent` | Text | `RecipeOutput` / `WeeklyScheduleOutput` | Single recipe or a 7-day meal schedule, filtered by diet safety rules. |
| `mood_checkin_agent` | Text (transcript) | `MoodCheckInAnalysisResult` | Emotion, stress (0–100), stress indicators, urgency, and summary from a voice journal. |
| `test_agent` | Text | Plain string | LLM connectivity smoke test. |

### Safety & Clinical Guardrails

Several guards are deterministic (applied in code, not just prompted):

- **Nutrition target engine** — Mifflin-St Jeor BMR → TDEE; protein adjusted by kidney stage (1.0 / 0.8 / 0.6 g/kg); carbohydrates capped at 45% of calories when diabetes is present; calories floored at 1200.
- **Daily summary alerts** — BP > 140/90, glucose > 180 mg/dL, SpO₂ < 95%.
- **Diet plan guards** — protein cap for kidney disease, low-GI foods for diabetes, hard stops for allergies and restrictions, plus religious/dietary rules (no pork/alcohol, no beef, kosher, vegetarian, vegan).
- **Recipe guards** — never include `avoid_foods`, respect `limit_foods` and allergies, no medical claims, no medication advice.
- **Correlation engine** — output is phrased as *association*, never causation ("may be associated with", "possible contributing factors").

---

## LLM Provider Configuration

Every agent resolves its provider and model from environment variables:

1. `LLM_PROVIDER` / `LLM_MODEL` — global defaults.
2. `<AGENT_NAME>_LLM_PROVIDER` / `<AGENT_NAME>_LLM_MODEL` — per-agent overrides (agent name uppercased, non-alphanumerics → `_`).

Supported provider strings follow LangChain conventions: `bedrock` (default), `ollama`, `openai`, `anthropic`, and any other provider with the relevant `langchain-*` package installed. Bedrock resolves via `init_chat_model(..., model_provider="bedrock_converse")` and falls back to the plain `bedrock` path.

Bedrock model id precedence: `BEDROCK_MODEL_ID` → `INFERENCE_PROFILE_ID` → `CLAUDE_3_7_PROFILE_ID` → hard-coded `apac.anthropic.claude-3-7-sonnet-20250219-v1:0`.

### Per-Agent Overrides

| Agent | Provider variable | Model variable |
| --- | --- | --- |
| diet_plan_agent | `DIET_PLAN_AGENT_LLM_PROVIDER` | `DIET_PLAN_AGENT_LLM_MODEL` |
| daily_summary_agent | `DAILY_SUMMARY_AGENT_LLM_PROVIDER` | `DAILY_SUMMARY_AGENT_LLM_MODEL` |
| food_agent | `FOOD_AGENT_LLM_PROVIDER` | `FOOD_AGENT_LLM_MODEL` |
| ingredient_scanner_agent | `INGREDIENT_SCANNER_AGENT_LLM_PROVIDER` | `INGREDIENT_SCANNER_AGENT_LLM_MODEL` |
| nutrition_calculator_agent | `NUTRITION_CALCULATOR_AGENT_LLM_PROVIDER` | `NUTRITION_CALCULATOR_AGENT_LLM_MODEL` |
| nutritionist_agent | `NUTRITIONIST_AGENT_LLM_PROVIDER` | `NUTRITIONIST_AGENT_LLM_MODEL` |
| report_agent | `REPORT_AGENT_LLM_PROVIDER` | `REPORT_AGENT_LLM_MODEL` |
| report_merge_agent | `REPORT_MERGE_AGENT_LLM_PROVIDER` | `REPORT_MERGE_AGENT_LLM_MODEL` |
| summary_agent | `SUMMARY_AGENT_LLM_PROVIDER` | `SUMMARY_AGENT_LLM_MODEL` |
| mood_checkin_agent | `MOOD_CHECKIN_AGENT_LLM_PROVIDER` | `MOOD_CHECKIN_AGENT_LLM_MODEL` |
| diet_chart_agent | `DIET_CHART_AGENT_LLM_PROVIDER` | `DIET_CHART_AGENT_LLM_MODEL` |
| recipe_suggestion_agent | `RECIPE_SUGGESTION_AGENT_LLM_PROVIDER` | `RECIPE_SUGGESTION_AGENT_LLM_MODEL` |
| nutrition_recalculator_agent | *(inherits global)* | `NUTRITION_RECALCULATOR_AGENT_LLM_MODEL` |
| test_agent | *(inherits global)* | `TEST_AGENT_LLM_MODEL` |

Example — run the diet plan agent locally while everything else uses Bedrock:

```bash
LLM_PROVIDER=bedrock
LLM_MODEL=apac.anthropic.claude-3-7-sonnet-20250219-v1:0

DIET_PLAN_AGENT_LLM_PROVIDER=ollama
DIET_PLAN_AGENT_LLM_MODEL=glm-4.7-flash:latest
```

### Debugging

```bash
LLM_DEBUG_LOG_PROMPTS=true        # redact + log prompts (per agent too)
LLM_DEBUG_MAX_CHARS=4000          # prompt payload truncation, floor 256
```

Debug payloads redact any `data` key and truncate strings, so base64 image payloads do not leak into logs. Currently wired into `diet_plan_agent`, `diet_chart_agent`, and `recipe_suggestion_agent`.

> Per-agent configs are resolved at import time — restart the process after changing `.env`.

---

## API Reference

Canonical prefix: **`/api/v1`**. Interactive docs: `/docs` (Swagger) and `/redoc` (ReDoc). Full details in [`docs/api-reference.md`](docs/api-reference.md) and [`backend/MOBILE_INTEGRATION_GUIDE.md`](backend/MOBILE_INTEGRATION_GUIDE.md).

**81 HTTP endpoints** across 8 routers — auth (6), AI (10), health (25), recipes (13), users (4), payments (2), packages (5), admin (16) — plus 2 app-level routes (`/` and `/health`).

### Authentication — `/api/v1/auth`

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/signup` | — | Register; creates user, encrypted PII, persona, `user` role, and a 7-day trial subscription. |
| POST | `/api/v1/auth/signin` | — | Exchange email + password for access and refresh tokens. |
| POST | `/api/v1/auth/refresh-token` | — | Exchange a refresh token for a new access token. |
| POST | `/api/v1/auth/forgot-password` | — | Start a password reset. Always returns a generic message (no user enumeration). |
| POST | `/api/v1/auth/reset-password` | — | Complete a password reset with the emailed token. |
| DELETE | `/api/v1/auth/delete-account` | Bearer | Full HIPAA-style deletion: removes PII, anonymises persona, soft-deletes the user, writes audit records. |

### AI — `/api/v1/ai`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/ai/upload-food` | Multi-image food recognition → per-item and total nutrition. Subject to the daily upload quota (`429`). |
| POST | `/api/v1/ai/scan-ingredients` | Single packaging image → ingredients, ratings, NutriGrade, allergens, age limits. Shares the upload quota. |
| POST | `/api/v1/ai/upload-report` | Multi-file medical report upload → merged EHR data, structured profile, version number. |
| POST | `/api/v1/ai/nutrition-advice` | Personalised nutritionist advice. Also persists the meal (`source="nutrition_advice"`). Subject to the daily nutrition-query quota. |
| POST | `/api/v1/ai/calculate-nutrition` | Nutrition from plain-text food items. Does not count against quotas and does not save a meal. |
| POST | `/api/v1/ai/recalculate-nutrition` | Recompute nutrition after the user corrects identified foods. |
| GET | `/api/v1/ai/report-data` | Current structured health profile from reports. |
| DELETE | `/api/v1/ai/report-data` | Delete all structured medical report history. |
| GET | `/api/v1/ai/nutrition-data` | Paginated meal history (`start_date`, `end_date`, `page`, `page_size`). |
| GET | `/api/v1/ai/nutrition-data/today` | Today's meal entries. |

### Health Timeline — `/api/v1/health`

**Profile & Targets**

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/v1/health/profile/current` | Current structured health profile. |
| GET | `/api/v1/health/targets/current` | Current nutrition target (auto-calculated if absent). |
| POST | `/api/v1/health/targets` | Set a manual nutrition target. |
| GET | `/api/v1/health/targets/adherence` | Adherence vs. target for a date. |

**Meals**

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/meals/draft-from-image` | AI meal draft from photos. Not persisted. |
| POST | `/api/v1/health/meals/confirm` | Persist a confirmed meal with nutrition, date, and time. |
| GET | `/api/v1/health/meals/today-summary` | Today's meal nutrition totals. |
| GET | `/api/v1/health/meals/history` | Paginated meal history. |

**Vitals**

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/vitals` | Log a batch of vitals manually. |
| POST | `/api/v1/health/vitals/import-csv` | Import vitals from a CSV file. |
| POST | `/api/v1/health/vitals/device-sync` | Sync vitals from a wearable (Health Connect / HealthKit shape). Idempotent. |
| GET | `/api/v1/health/vitals/daily` | Vitals for one day. |
| GET | `/api/v1/health/vitals/history` | Paginated vital history. |

**Mood**

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/mood/checkin` | Audio check-in → Transcribe → mood/stress analysis → persisted. Requires `consent=true`. |
| GET | `/api/v1/health/mood/history` | Paginated mood check-in history. |

**Insights**

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/v1/health/insights/daily` | Insights for a single day. |
| GET | `/api/v1/health/insights/weekly` | Insights for the trailing 7 days. |
| GET | `/api/v1/health/insights/monthly` | Insights for the trailing 30 days. |

**Diet Plan**

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/diet-plan/generate` | Generate a new diet plan (`trigger="manual"`). |
| GET | `/api/v1/health/diet-plan/current` | Active diet plan. |
| GET | `/api/v1/health/diet-plan/history` | All past plans. |
| GET | `/api/v1/health/diet-plan/today` | Today's meals from the active plan. |

**Daily Summary**

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/daily-summary/generate` | Generate a summary for a given date. |
| GET | `/api/v1/health/daily-summary` | Summary for a date. |
| GET | `/api/v1/health/daily-summary/recent` | The last N summaries (default 7). |

### Recipes — `/api/v1/health/recipes`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/health/recipes/diet-profiles/upload` | Upload a diet chart → AI extraction of restrictions. |
| POST | `/api/v1/health/recipes/diet-profiles/manual` | Create a diet profile manually. |
| GET | `/api/v1/health/recipes/diet-profiles` | All diet profiles. |
| GET | `/api/v1/health/recipes/diet-profiles/active` | The active diet profile. |
| GET | `/api/v1/health/recipes/diet-profiles/{profile_id}` | A specific diet profile. |
| PATCH | `/api/v1/health/recipes/diet-profiles/{profile_id}` | Confirm extracted restrictions or edit the profile. |
| POST | `/api/v1/health/recipes/suggest` | Generate a single recipe. |
| POST | `/api/v1/health/recipes/generate-schedule` | Generate a 7-day meal schedule. |
| GET | `/api/v1/health/recipes/schedules/current` | Current weekly schedule. |
| GET | `/api/v1/health/recipes` | Recipe history / favourites (`meal_type`, `favorites_only`, `limit`). |
| GET | `/api/v1/health/recipes/{recipe_id}` | Full recipe details. |
| PATCH | `/api/v1/health/recipes/{recipe_id}/favorite` | Toggle favourite status. |
| POST | `/api/v1/health/recipes/{recipe_id}/track` | Track a recipe (`cooked` / `ate` / `skipped` / `replaced`). |

### Users — `/api/v1/users`

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/v1/users/me` | Current user's profile (PII, persona, activity level, timezone). |
| PUT | `/api/v1/users/me` | Update profile. Email cannot be changed. |
| GET | `/api/v1/users/me/usage` | Usage stats: plan, status, uploads today, remaining, max daily. |
| DELETE | `/api/v1/users/me` | Soft-delete the account (GDPR). |

### Payments & Packages

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/payment` | Bearer | Create a payment record (`status="pending"`). Stripe integration is a placeholder. |
| GET | `/api/v1/payment/history` | Bearer | Payment history. |
| GET | `/api/v1/packages/` | — | List subscription packages. |
| GET | `/api/v1/packages/{package_id}` | — | Get one package. |
| POST | `/api/v1/packages/` | Admin | Create a package. |
| PUT | `/api/v1/packages/{package_id}` | Admin | Update a package. |
| DELETE | `/api/v1/packages/{package_id}` | Admin | Soft-delete (deactivate) a package. |

### Admin — `/api/v1/admin`

All admin endpoints require the `X-Admin-Key` header.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/v1/admin/users` | List users with roles (`skip`, `limit`). |
| GET | `/api/v1/admin/audit-logs` | Audit logs (`skip`, `limit`, `action`). |
| PUT | `/api/v1/admin/users/{user_id}/role` | Replace a user's role (`user` / `admin`). |
| PUT | `/api/v1/admin/users/{user_id}/package` | Assign a package, with optional `duration_days`. |
| GET | `/api/v1/admin/users/{user_id}/subscription` | A user's active subscription and package. |
| GET | `/api/v1/admin/packages` | List active packages. |
| POST | `/api/v1/admin/packages` | Create a package (`billing_period`: free / monthly / yearly). |
| PUT | `/api/v1/admin/packages/{package_id}` | Update a package. |
| DELETE | `/api/v1/admin/packages/{package_id}` | Deactivate a package. |
| POST | `/api/v1/admin/packages/{package_id}/activate` | Reactivate a package. |
| POST | `/api/v1/admin/jobs/run-daily-summaries` | Trigger `daily_summary_job` manually. |
| POST | `/api/v1/admin/jobs/run-weekly-plan-refresh` | Trigger `weekly_plan_refresh_job` manually. |
| GET | `/api/v1/admin/token-stats/daily` | Daily token usage (`days`, 1–365). |
| GET | `/api/v1/admin/token-stats/models` | Token usage aggregated per model. |
| GET | `/api/v1/admin/token-stats/top-consumers` | Top token-consuming users (`limit`). |
| GET | `/api/v1/admin/users/{user_id}/token-stats` | Token stats for one user. |

### App-Level

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/` | Liveness banner. |
| GET | `/health` | Health check with a database connectivity probe. |

---

## Data Model

30+ PostgreSQL tables managed by Alembic (20 revisions, head `1ea7e4b8e1b9`).

### Identity & Billing

| Table | Purpose |
| --- | --- |
| `users` | Accounts — credentials, `is_active`, `deleted_at` (soft delete). |
| `roles` / `user_roles` | Role definitions (`user`, `admin`) and assignments. |
| `packages` | Subscription packages — price, `billing_period`, `is_active`. |
| `subscriptions` | User subscriptions — `plan_type`, `status`, `end_date`, `package_id`. |
| `payments` | Payment records. |
| `upload_limits` | Per-user daily upload and nutrition query counters. |
| `token_usage` | Per-request LLM token accounting. |
| `audit_logs` | General security audit trail. |
| `password_resets` | Password reset tokens (stored hashed). |

### Patient & Clinical

| Table | Purpose |
| --- | --- |
| `patient_pii` | Encrypted PII: `full_name_encrypted`, `email_encrypted`, `phone_number_encrypted`. |
| `patient_persona` | Non-PHI profile: `date_of_birth`, `gender`, `blood_group`, `height_cm`, `weight_kg`, `activity_level`, `timezone`, `current_location`, `birth_place`, `nationality`, `cuisine_preference`. |
| `hipaa_audit_logs` | PHI access / create / update / delete / encrypt / decrypt / anonymise trail. |
| `medical_reports` | Report versions — `version`, `report_category`, `is_current`, `raw_payload`, `structured_summary`. |
| `medical_report_entities` | Extracted clinical entities with value, unit, reference range, confidence. |
| `medical_condition_snapshots` | Point-in-time condition status per report category. |
| `lab_results` | Individual lab values with `abnormal_flag` and reference ranges. |
| `medication_schedules` | Prescribed medications with dosage, schedule, and with-food flags. |

### Timeline & Planning

| Table | Purpose |
| --- | --- |
| `meal_events` | Logged meals with macro totals, `meal_date`, `meal_time`, `source`, `status`. |
| `meal_items` | Individual food items within a meal (name, quantity, role, preparation, confidence). |
| `meal_media` | Source image/audio per meal. |
| `vital_events` | Vitals — `value_primary`, `value_secondary`, `unit`, `captured_at`, `source`. Deterministic UUIDv5 for idempotent device sync. |
| `mood_checkins` | Voice/text mood entries — transcript, mood label, energy, stress, sleep quality, symptom flags. |
| `correlation_insights` | Derived meal↔vital↔mood associations with confidence tier and evidence. |
| `nutrition_targets` | Daily macro targets — `source` (`calculated` / `manual`), `calculation_basis`, `is_active`. |
| `diet_plans` | 7-day plans — `valid_from`, `valid_until`, `trigger`, `calorie_target`, `is_active`. |
| `diet_plan_meals` | Plan meals — `day_of_week` (0 = Monday … 6 = Sunday), `meal_type`, `foods`. |
| `daily_summaries` | Daily narrative, stats snapshot, adherence score, alerts, `data_quality`. |

### Recipes

| Table | Purpose |
| --- | --- |
| `diet_profiles` | Extracted diet restrictions and preferences, with `extraction_status`. |
| `generated_recipes` | AI-generated recipes with full detail and estimated nutrition. |
| `weekly_meal_schedules` | Weekly meal plans referencing recipes. |
| `recipe_tracking_entries` | Links recipes to the meal tracker (`cooked` / `ate` / `skipped` / `replaced`). |

### Legacy

`nutrition_data` and `report_data` (blob stores) were dropped in migration `8a44d0f5501f`. Their replacements are the normalised tables above.

---

## Security & Privacy

### Authentication

- **JWT** via `python-jose`, `HS256` by default. Tokens carry a `type` claim (`access` / `refresh`) and are rejected on type mismatch.
- Access tokens: `ACCESS_TOKEN_EXPIRE_MINUTES` (`.env.example` sets 30; the in-code default is 43200 — set it explicitly).
- Refresh tokens: `REFRESH_TOKEN_EXPIRE_DAYS` (7). The refresh endpoint issues a new access token only.
- Password reset tokens: hashed with Argon2 before storage, `PASSWORD_RESET_TOKEN_EXPIRE_HOURS` (1) expiry, single-use via `used_at`.
- Forgot-password always returns the same message whether or not the email exists.

### Password Storage

- **Argon2id** (`$argon2id$...`) as the primary algorithm, with bcrypt as a fallback.
- Maximum password length 1024 UTF-8 bytes.
- Passwords longer than bcrypt's 72-byte limit are SHA-256 pre-hashed to avoid silent truncation.
- Minimum strength requirement: **6 characters**.

### Encryption at Rest

- **AES-256-GCM** for `patient_pii`. The key comes from `ENCRYPTION_KEY` (base64, exactly 32 bytes).
- A fresh 12-byte random nonce per encryption, prepended to the ciphertext.
- Generate a key with `uv run python scripts/generate_encryption_key.py`. Never commit it; use different keys per environment.

### Audit Logging

- `audit_logs` — authentication events, authorisation failures, and data modifications.
- `hipaa_audit_logs` — PHI-specific trail recording `phi_access`, `phi_create`, `phi_update`, `phi_delete`, `phi_encrypt`, `phi_decrypt`, and `phi_anonymize`, with IP address, user agent, and field-level detail.

### Account Deletion

- `DELETE /api/v1/auth/delete-account` — deletes encrypted PII, anonymises the persona (nulls `user_id`, stamps `anonymized_at`), soft-deletes the user, and writes audit records.
- `DELETE /api/v1/users/me` — lighter GDPR soft delete.

### Admin Access

Admin endpoints authenticate with the **`X-Admin-Key` header** compared against `ADMIN_KEY`, not with a JWT role claim. The `roles` / `user_roles` tables and the `require_role` / `require_user` dependencies exist and are fully implemented, but are not currently wired into any route.

> `ADMIN_KEY` is **not** included in `backend/.env.example` — set it yourself before using any admin endpoint.

### Image & Document Handling

- Uploads are capped at 5 MB and re-encoded to WebP when they exceed the Bedrock Converse payload limit (~2.8 MB after base64 expansion), preserving detail down to 2048 px on the longest edge.
- PDF uploads are converted to JPEG and **only the first page** is processed.
- Supported image MIME types: `image/jpeg`, `image/png`, `image/webp`.

### Audio Handling

- Mood check-in audio is uploaded to a private S3 bucket, transcribed via AWS Transcribe, and the S3 object is deleted in a `finally` block regardless of outcome.
- Max upload size 12 MB. Formats: `.wav`, `.mp3`, `.mp4`, `.m4a`.

---

## Subscription Model

| | Free Tier | Paid Tier |
| --- | --- | --- |
| Food image uploads | `FREE_TIER_DAILY_UPLOAD_LIMIT` (default 2/day) | Unlimited |
| Nutrition queries | `FREE_TIER_DAILY_NUTRITION_LIMIT` (default 2/day) | Unlimited |
| Medical report analysis | ✅ | ✅ |
| Health timeline, diet plans, recipes | ✅ | ✅ |
| Priority support | — | ✅ |

- New signups receive a **7-day trial** on the paid tier.
- Daily counters live in `upload_limits`, one row per user per day, reset at midnight UTC.
- When a paid subscription expires, admin-assigned packages auto-extend by 30 days; otherwise the user is downgraded to `free`.
- Usage stats (`GET /api/v1/users/me/usage`) report plan, status, uploads used today, remaining, and the daily maximum, plus trial days remaining where applicable.

---

## Background Jobs

Two APScheduler cron jobs run on the hour and then check each user's **local** time (from `patient_persona.timezone`), so a user in Kolkata gets their 21:00 summary at 21:00 IST rather than 21:00 UTC.

| Job | Fires when (user-local) | Action |
| --- | --- | --- |
| `daily_summary_job` | Hour == 21, once per local date | Generates the daily summary for that date. Skipped if one exists or there is insufficient data. |
| `weekly_plan_refresh_job` | Monday at 06:00 (`trigger="scheduled_weekly"`), or when the active plan has expired (`trigger="plan_expired"`) | Generates a fresh 7-day diet plan and deactivates the previous one. |

> The scheduler is currently **disabled** — `start_scheduler()` is commented out in the application lifespan. Trigger the jobs manually with `POST /api/v1/admin/jobs/run-daily-summaries` and `POST /api/v1/admin/jobs/run-weekly-plan-refresh`, or re-enable it in `backend/src/presentation/api/routes.py`.

---

## Real-Time Events

The Socket.IO server is mounted on the same ASGI app as the HTTP API (`backend/main.py` exports `socket_app`), so both are served from one port.

| Event | Direction | Payload |
| --- | --- | --- |
| `food_analysis_complete` | Server → client | Analysis result, broadcast to all connected clients. |

`index.html` in the repository root is a browser-based event-stream viewer for this channel.

> The `socket_manager.sio` instance used to emit is currently **separate** from the instance mounted in `routes.py`, so emissions may not reach connected clients as written. See [Known Limitations](#known-limitations).

---

## Admin Dashboard

A standalone Streamlit app in `admin_frontend/`:

```bash
cd admin_frontend
pip install -r requirements.txt

export API_BASE_URL=http://localhost:8011/api/v1
export ADMIN_KEY=<your-admin-key>

streamlit run app.py
```

It covers user management (list, roles, package assignment, subscription lookup), package CRUD, audit log browsing, and token usage analytics.

---

## Development

### Backend

```bash
cd backend
uv sync

make dev              # hot-reload server on :8000
make test             # pytest
make test-coverage    # pytest + coverage report
make lint             # ruff check
make format           # ruff format
make check-env        # validate settings load
make generate-key     # new AES-256-GCM key
```

### Database Migrations

```bash
make create-migration MSG="describe the change"   # autogenerate a revision
make migrate                                     # upgrade head
make migration-history                           # full history
make migration-current                           # applied revision
make migration-heads                             # head revisions
make force-migrate                               # downgrade -1 then upgrade head
make reset-db                                    # drop everything and rebuild
```

### Token Usage Tracking

```bash
uv run python scripts/test_nutrition_calculator_with_reference.py
uv run python scripts/test_summary_agent.py
uv run python scripts/test_signup_trial.py
uv run python scripts/get_debug_token.py
```

---

## Deployment

### Docker Compose (Local / Staging)

```bash
docker compose up -d --build
```

The `backend` service waits for the PostgreSQL healthcheck, runs `alembic upgrade head`, and starts Uvicorn with `--reload`. For production, drop `--reload`, set `DEBUG=False`, and use a strong `JWT_SECRET_KEY` and `ENCRYPTION_KEY`.

### AWS

| Component | Location |
| --- | --- |
| Build pipeline | `backend/buildspec.yml` |
| Deployment | `backend/appspec.yml` |
| Infrastructure | `backend/infra/cloudformation/` |
| Parameter reference | `aws-parameters.md` |
| S3 bucket for mood audio | `backend/infra/cloudformation/mood-checkins-s3.yml` |

---

## Troubleshooting

### Database connection errors

```bash
docker compose ps postgres
docker compose logs postgres
pg_isready -h localhost -p 5437          # host port is 5437 in compose
```

Note the port mapping: compose publishes host **5437** → container **5432**. The compose `DATABASE_URL` correctly uses the in-network address.

### Migration errors

```bash
cd backend
uv run alembic current
uv run alembic history
uv run alembic heads
uv run alembic upgrade head
```

Multiple heads indicate a branch that was never merged — `alembic heads` shows them; `02c57b282908` merges the historical pair.

### LLM / Bedrock errors

```bash
uv run python test_model.py        # prints the resolved model + provider
```

Check that `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are both set (a partial pair raises), that `ASIA…`-prefixed keys also set `AWS_SESSION_TOKEN`, and that `BEDROCK_MODEL_ID` in `.env` is not still the placeholder string.

### Authentication errors

- `401` — missing or invalid access token, or the token is a refresh token.
- `403` — the account is inactive or soft-deleted.
- Admin `403` — `X-Admin-Key` does not match `ADMIN_KEY`.
- Password reset returns "not found" for every email by design; check `password_resets` and the audit log.

### Image upload rejected

- Max 5 MB.
- MIME must be `image/jpeg`, `image/png`, or `image/webp`.
- PDFs are read via Poppler (`poppler-utils`); if it is missing the API returns a 500 with a "Poppler is not installed" message.

---

## Known Limitations

Documented for accuracy — these are current behaviours, not bugs to be surprised by later.

1. **Rate limiting is configured but not enforced.** `RATE_LIMIT_LOGIN_ATTEMPTS` and `RATE_LIMIT_LOGIN_WINDOW_MINUTES` exist in settings but no middleware reads them. Login is not throttled.
2. **The scheduler is disabled.** Daily summaries and weekly plan refreshes only run when triggered manually via the admin job endpoints.
3. **Two Socket.IO server instances.** The emitting instance in `socket_manager.py` is not the mounted one in `routes.py`, so `food_analysis_complete` may not reach clients.
4. **RabbitMQ is publish-only.** The `food_events` queue is published to but never consumed in production code, and no RabbitMQ service is defined in `docker-compose.yml`. The event listener is a placeholder.
5. **Only the first page of a PDF is processed.**
6. **`ADMIN_KEY` is missing from `.env.example`**, and admin access is API-key based rather than role based.
7. **Access token expiry defaults disagree** — `settings.py` defaults to 43200 minutes while `.env.example` documents 30. Set it explicitly.
8. **Password minimum is 6 characters**, despite the reset-password docstring claiming 8 with complexity rules.
9. **Payment processing is a placeholder** — a `payments` row is written with `status="pending"`; no Stripe SDK is wired in.
10. **Duplicate endpoints exist** for convenience — `GET /ai/report-data` ≡ `GET /health/profile/current`, and `GET /ai/nutrition-data` ≡ `GET /health/meals/history`.
11. **Trailing-slash inconsistency** — `/api/v1/packages/` (with slash) vs `/api/v1/payment` (without).
12. **Agents have no tools, no conversation memory, and no checkpointer.** All are single-shot calls with context passed explicitly.
13. **Langfuse tracing has been removed**; the module remains as a no-op stub. Observability is via structured logging, `get_chat_model_diagnostics()`, optional prompt debugging, and the token-usage service.
14. **Per-agent LLM config is resolved at import time** — restart the process after editing `.env`.

---

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/api-reference.md`](docs/api-reference.md) | Full API reference with request/response contracts. |
| [`backend/MOBILE_INTEGRATION_GUIDE.md`](backend/MOBILE_INTEGRATION_GUIDE.md) | Mobile developer guide — every endpoint, screen flows, error reference. |
| [`docs/recipe-feature-guide.md`](docs/recipe-feature-guide.md) | Recipe suggestion feature guide. |
| [`docs/longitudinal-health-implementation.md`](docs/longitudinal-health-implementation.md) | Approved direction and tracker for the longitudinal health model. |
| [`docs/dietguard-implementation-status-2026-03-13.md`](docs/dietguard-implementation-status-2026-03-13.md) | Implementation status report and roadmap progress. |
| [`backend/README.md`](backend/README.md) | Backend-specific setup and command reference. |
| [`DOCKER_README.md`](DOCKER_README.md) | Docker-specific setup and operations. |
| [`backend/CHANGELOG.md`](backend/CHANGELOG.md) | Change history. |
| Swagger UI | http://localhost:8011/docs |
| ReDoc | http://localhost:8011/redoc |

---

## License

MIT — see [`LICENSE`](LICENSE). Copyright © 2025 Anamul Haque.
