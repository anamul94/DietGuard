# DietGuard Backend

FastAPI backend for **DietGuard AI** — multimodal analysis of medical reports and food images, a longitudinal health timeline, personalised diet plans and recipes, and clinical daily summaries.

API version `2.0.0`. All application endpoints live under **`/api/v1`**.

> The [root README](../README.md) is the main project overview. This document focuses on backend specifics.

---

## Contents

- [Stack](#stack)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [LLM / Agent Configuration](#llm--agent-configuration)
- [API Endpoints](#api-endpoints)
- [Architecture](#architecture)
- [Database](#database)
- [Security](#security)
- [Subscriptions](#subscriptions)
- [Background Jobs](#background-jobs)
- [WebSocket / Socket.IO](#websocket--socketio)
- [Development](#development)
- [Migrations](#migrations)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Stack

| Layer | Technology |
| --- | --- |
| Framework | FastAPI ≥ 0.117 (Python ≥ 3.11), Uvicorn |
| Real-time | python-socketio 5.10 (ASGI) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migrations | Alembic (20 revisions, head `1ea7e4b8e1b9`) |
| Auth | python-jose (JWT), Argon2id (`argon2-cffi`) |
| Encryption | cryptography — AES-256-GCM |
| AI | LangChain ≥ 0.3 (`init_chat_model`), LangGraph ≥ 0.6 |
| LLM | AWS Bedrock (default) or any LangChain provider; `langchain-aws`, `langchain-ollama` |
| Speech | AWS Transcribe (batch) |
| Scheduling | APScheduler |
| Validation | Pydantic v2, pydantic-settings |
| Documents | `pdf2image` + Poppler |

---

## Requirements

- Python 3.11+
- PostgreSQL 14+ (15 used in Docker)
- Redis 7+ (optional — legacy blob cache only)
- AWS credentials with Bedrock access, **or** a local Ollama model
- Poppler (`poppler-utils`) for PDF conversion

---

## Quick Start

### With Docker Compose

From the repository root:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set JWT_SECRET_KEY, ENCRYPTION_KEY, AWS credentials

docker compose up -d
make seed          # roles + subscription packages
curl http://localhost:8011/health
```

The backend container waits for PostgreSQL, runs `alembic upgrade head` automatically, then starts Uvicorn with `--reload`.

| Service | Host port | Container port |
| --- | --- | --- |
| Backend API | 8011 | 8000 |
| PostgreSQL | 5437 | 5432 |

### Manual

```bash
cd backend
uv sync

cp .env.example .env
# Edit .env with your configuration

uv run alembic upgrade head
uv run python scripts/seed_roles.py
uv run python scripts/seed_packages.py

uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The entry point is `backend/main.py`, which exports the Socket.IO-wrapped ASGI app as `app`. Start it with `uvicorn main:app`.

### Redis (optional)

```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine \
  redis-server --requirepass myredissecret
```

Redis is only used for the legacy report/nutrition blob cache (`dietguard:report:{user_id}` 12 h TTL, `dietguard:nutrition:{user_id}` 24 h TTL). It is not used for rate limiting or sessions.

---

## Environment Variables

### Database

```bash
DATABASE_URL=postgresql+asyncpg://dietguard:dietguard123@localhost:5432/dietguard
POSTGRES_USER=dietguard
POSTGRES_PASSWORD=dietguard123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dietguard
```

### JWT & Security

```bash
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_TOKEN_EXPIRE_HOURS=1
RATE_LIMIT_LOGIN_ATTEMPTS=5          # configured, not currently enforced
RATE_LIMIT_LOGIN_WINDOW_MINUTES=15   # configured, not currently enforced
ADMIN_KEY=your_secure_admin_api_key_here   # NOT in .env.example — set it yourself
```

> `ADMIN_KEY` is **absent from `.env.example`**. Admin routes compare the `X-Admin-Key` header against this value. Without it, the default is the insecure placeholder `your_secure_admin_api_key_here`.

### HIPAA Encryption (required)

```bash
# Generate: uv run python scripts/generate_encryption_key.py
ENCRYPTION_KEY=your-base64-encoded-32-byte-encryption-key-here
```

Encrypts `patient_pii.full_name`, `.email`, and `.phone_number` with AES-256-GCM. Never commit this key; use distinct keys per environment.

### Subscription Limits

```bash
FREE_TIER_DAILY_UPLOAD_LIMIT=2
FREE_TIER_DAILY_NUTRITION_LIMIT=2
```

### AWS / Bedrock

```bash
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_SESSION_TOKEN=...          # required for temporary (ASIA…) credentials
AWS_PROFILE=...                # mutually exclusive with explicit keys
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=...           # takes precedence over INFERENCE_PROFILE_ID
INFERENCE_PROFILE_ID=global.anthropic.claude-sonnet-4-6
```

> The `.env.example` ships `BEDROCK_MODEL_ID=optional_explicit_model_or_inference_profile_id` as a placeholder. **Replace or remove it** — otherwise that literal string becomes the model id.

### AWS Transcribe (mood check-ins)

```bash
TRANSCRIBE_S3_BUCKET=your_private_bucket_name
TRANSCRIBE_S3_PREFIX=mood-checkins/
TRANSCRIBE_LANGUAGE_CODE=en-US
TRANSCRIBE_TIMEOUT_SECONDS=180
TRANSCRIBE_POLL_INTERVAL_SECONDS=2
MAX_MOOD_AUDIO_MB=12
```

The audio object is deleted from S3 in a `finally` block immediately after the transcription attempt. Configure a bucket lifecycle rule as a backstop (`infra/cloudformation/mood-checkins-s3.yml`).

### Application

```bash
APP_NAME=DietGuard
DEBUG=True
LOG_LEVEL=INFO
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=myredissecret
```

---

## LLM / Agent Configuration

### Global

```bash
LLM_PROVIDER=bedrock
LLM_MODEL=apac.anthropic.claude-3-7-sonnet-20250219-v1:0
LLM_DEBUG_LOG_PROMPTS=false
LLM_DEBUG_MAX_CHARS=4000
```

`LLM_PROVIDER` accepts any LangChain provider string — `bedrock` (default), `ollama`, `openai`, `anthropic`. Bedrock resolves through `init_chat_model(..., model_provider="bedrock_converse")` with a fallback to the plain `bedrock` path.

### Per-Agent Overrides

`<AGENT_NAME>_LLM_PROVIDER` and `<AGENT_NAME>_LLM_MODEL` override the globals per agent.

```bash
DIET_PLAN_AGENT_LLM_PROVIDER=ollama
DIET_PLAN_AGENT_LLM_MODEL=glm-4.7-flash:latest
REPORT_AGENT_LLM_PROVIDER=bedrock
REPORT_AGENT_LLM_MODEL=apac.anthropic.claude-3-7-sonnet-20250219-v1:0
MOOD_CHECKIN_AGENT_LLM_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

Full list of agent names and their environment variables:

| Agent | Purpose |
| --- | --- |
| `food_agent` | Food photo → per-item and total nutrition |
| `ingredient_scanner_agent` | Packaging label → ingredients, NutriGrade A–D |
| `report_agent` | Medical report → structured clinical entities |
| `report_merge_agent` | Merge report versions into a FHIR-inspired record |
| `diet_chart_agent` | Doctor's diet chart → restrictions and targets |
| `nutrition_calculator_agent` | Text food items → macros |
| `nutrition_recalculator_agent` | Recompute macros after user corrections |
| `nutritionist_agent` | Personalised meal advice |
| `summary_agent` | TTS-ready spoken summary |
| `daily_summary_agent` | End-of-day clinical narrative + alerts |
| `diet_plan_agent` | 7-day condition-aware diet plan |
| `recipe_suggestion_agent` | Single recipe or 7-day meal schedule |
| `mood_checkin_agent` | Emotion and stress from a transcribed journal |
| `test_agent` | LLM connectivity smoke test |

### Prompt Debugging

```bash
LLM_DEBUG_LOG_PROMPTS=true
LLM_DEBUG_MAX_CHARS=4000
```

Also available per agent (`<AGENT_NAME>_LLM_DEBUG_LOG_PROMPTS`). Debug payloads redact any `data` key and truncate strings, so base64 image payloads stay out of logs. Currently wired into `diet_plan_agent`, `diet_chart_agent`, and `recipe_suggestion_agent`.

> Per-agent LLM config is resolved at import time — restart the process after editing `.env`.

---

## API Endpoints

Base URL: `http://localhost:8000` · Prefix: `/api/v1` · Swagger: `/docs` · ReDoc: `/redoc` · Health: `/health`

**81 HTTP endpoints** across 8 routers — auth (6), AI (10), health (25), recipes (13), users (4), payments (2), packages (5), admin (16) — plus 2 app-level routes (`/` and `/health`).

### Authentication — `/api/v1/auth`

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/signup` | — | Register. Creates user, encrypted PII, persona, `user` role, 7-day trial subscription. |
| POST | `/signin` | — | Returns access + refresh tokens, subscription, patient profile. |
| POST | `/refresh-token` | — | Exchange a refresh token for a new access token. |
| POST | `/forgot-password` | — | Start a reset. Generic response regardless of whether the email exists. |
| POST | `/reset-password` | — | Complete a reset with the emailed token. |
| DELETE | `/delete-account` | Bearer | Full deletion: removes PII, anonymises persona, soft-deletes the user, writes audit records. |

### AI — `/api/v1/ai`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/upload-food` | Multi-image food recognition → `fooditem_details[]` + totals. Daily upload quota applies. |
| POST | `/scan-ingredients` | Packaging image → ingredients, ratings, NutriGrade, allergens, age limits. Shares the upload quota. |
| POST | `/upload-report` | Multi-file medical report → merged EHR data, structured profile, version number. |
| POST | `/nutrition-advice` | Personalised advice; also persists the meal. Daily nutrition-query quota applies. |
| POST | `/calculate-nutrition` | Nutrition from plain-text items. No quota, no persistence. |
| POST | `/recalculate-nutrition` | Recompute after user corrections. Requires `old_food_analysis`. |
| GET | `/report-data` | Current structured health profile. |
| DELETE | `/report-data` | Delete all structured report history. |
| GET | `/nutrition-data` | Paginated meal history. |
| GET | `/nutrition-data/today` | Today's meal entries. |

### Health — `/api/v1/health`

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/profile/current` | Structured health profile (report metadata, labs, medications, trends). |
| GET | `/targets/current` | Current nutrition target; auto-calculated if absent. |
| POST | `/targets` | Set a manual target. |
| GET | `/targets/adherence` | Per-metric adherence (`under` / `on_track` / `over`). |
| POST | `/meals/draft-from-image` | AI meal draft from photos. Not persisted. |
| POST | `/meals/confirm` | Persist a confirmed meal. |
| GET | `/meals/today-summary` | Today's meal nutrition totals. |
| GET | `/meals/history` | Paginated meal history. |
| POST | `/vitals` | Log a batch of vitals manually. |
| POST | `/vitals/import-csv` | Import vitals from CSV. |
| POST | `/vitals/device-sync` | Sync from a wearable. Idempotent via deterministic UUIDv5. |
| GET | `/vitals/daily` | Vitals for one day. |
| GET | `/vitals/history` | Paginated vital history. |
| POST | `/mood/checkin` | Audio check-in → Transcribe → mood analysis → persisted. Requires `consent=true`. |
| GET | `/mood/history` | Paginated mood history. |
| GET | `/insights/daily` | Single-day insights. |
| GET | `/insights/weekly` | Trailing 7-day insights. |
| GET | `/insights/monthly` | Trailing 30-day insights. |
| POST | `/diet-plan/generate` | Generate a new diet plan (`trigger="manual"`). |
| GET | `/diet-plan/current` | Active diet plan. |
| GET | `/diet-plan/history` | All past plans. |
| GET | `/diet-plan/today` | Today's meals from the active plan. |
| POST | `/daily-summary/generate` | Generate a summary for a date. |
| GET | `/daily-summary` | Summary for a date. |
| GET | `/daily-summary/recent` | The last N summaries (default 7). |

### Recipes — `/api/v1/health/recipes`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/diet-profiles/upload` | Upload a diet chart → AI extraction of restrictions. |
| POST | `/diet-profiles/manual` | Create a diet profile manually. |
| GET | `/diet-profiles` | All diet profiles. |
| GET | `/diet-profiles/active` | The active diet profile. |
| GET | `/diet-profiles/{profile_id}` | A specific profile. |
| PATCH | `/diet-profiles/{profile_id}` | Confirm or edit extracted restrictions. |
| POST | `/suggest` | Generate a single recipe. |
| POST | `/generate-schedule` | Generate a 7-day meal schedule. |
| GET | `/schedules/current` | Current weekly schedule. |
| GET | `` | Recipe history / favourites. |
| GET | `/{recipe_id}` | Full recipe details. |
| PATCH | `/{recipe_id}/favorite` | Toggle favourite. |
| POST | `/{recipe_id}/track` | Track as `cooked` / `ate` / `skipped` / `replaced`. |

### Users — `/api/v1/users`

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/me` | Current user's profile. |
| PUT | `/me` | Update profile. Email cannot be changed. |
| GET | `/me/usage` | Plan, status, uploads today, remaining, max daily, trial info. |
| DELETE | `/me` | Soft-delete the account (GDPR). |

### Payments & Packages

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/v1/payment` | Bearer | Create a payment record (`status="pending"`). Stripe is a placeholder. |
| GET | `/api/v1/payment/history` | Bearer | Payment history. |
| GET | `/api/v1/packages/` | — | List packages. |
| GET | `/api/v1/packages/{package_id}` | — | Get one package. |
| POST | `/api/v1/packages/` | Admin | Create a package. |
| PUT | `/api/v1/packages/{package_id}` | Admin | Update a package. |
| DELETE | `/api/v1/packages/{package_id}` | Admin | Deactivate a package. |

### Admin — `/api/v1/admin`

All require the `X-Admin-Key` header.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/users` | List users with roles. |
| GET | `/audit-logs` | Audit logs, filterable by `action`. |
| PUT | `/users/{user_id}/role` | Replace a user's role (`user` / `admin`). |
| PUT | `/users/{user_id}/package` | Assign a package, optional `duration_days`. |
| GET | `/users/{user_id}/subscription` | Active subscription and package. |
| GET | `/packages` | List active packages. |
| POST | `/packages` | Create a package. |
| PUT | `/packages/{package_id}` | Update a package. |
| DELETE | `/packages/{package_id}` | Deactivate a package. |
| POST | `/packages/{package_id}/activate` | Reactivate a package. |
| POST | `/jobs/run-daily-summaries` | Trigger the daily summary job manually. |
| POST | `/jobs/run-weekly-plan-refresh` | Trigger the weekly plan refresh manually. |
| GET | `/token-stats/daily` | Daily token usage. |
| GET | `/token-stats/models` | Token usage per model. |
| GET | `/token-stats/top-consumers` | Top token-consuming users. |
| GET | `/users/{user_id}/token-stats` | Token stats for one user. |

### App-Level

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/` | Liveness banner. |
| GET | `/health` | Health check with a database probe. |

Full contracts: [`../docs/api-reference.md`](../docs/api-reference.md) and [`MOBILE_INTEGRATION_GUIDE.md`](MOBILE_INTEGRATION_GUIDE.md).

---

## Architecture

Clean layering under `src/`:

```
src/
├── presentation/
│   ├── api/          8 routers: auth, ai_agent, health, recipe, user, payment, package, admin
│   └── schemas/      Pydantic request/response models
├── application/
│   └── services/     13 service classes (static methods, session-first)
├── domain/
│   ├── entities/
│   └── enums/
└── infrastructure/
    ├── agents/       14 AI agents
    ├── graphs/       LangGraph correlation workflow
    ├── database/     SQLAlchemy models + async engine
    ├── auth/         JWT, password hashing, dependencies
    ├── security/     AES-256-GCM encryption service
    ├── config/       Settings
    ├── scheduler/    APScheduler + jobs
    ├── messaging/    RabbitMQ client (publish-only)
    ├── websocket/    Socket.IO manager
    └── utils/        Image, transcription, nutrition, logging helpers
```

### Application Services

| Service | Responsibility |
| --- | --- |
| `auth_service` | Signup, signin, password reset, account deletion. |
| `audit_service` | General security audit trail. |
| `hipaa_audit_service` | PHI access/modification trail. |
| `patient_service` | Encrypted PII + persona, anonymisation on deletion. |
| `health_timeline_service` | Report syncing and versioning, meals, vitals, mood, insights. |
| `nutrition_target_service` | Deterministic BMR/TDEE/macro engine. No LLM. |
| `diet_plan_service` | 7-day plan generation and history. |
| `daily_summary_service` | End-of-day summary generation. |
| `recipe_service` | Diet profiles, recipes, schedules, tracking. |
| `report_comparison_service` | Lab trend classification and worsening detection. |
| `subscription_service` | Plans, quotas, trials, expiry downgrade. |
| `token_usage_service` | LLM token accounting and analytics. |

### Health Correlation Graph

`src/infrastructure/graphs/` implements a two-node LangGraph workflow — `START → compute_associations → build_narrative → END`. It is **deterministic and LLM-free**.

Post-meal windows and delta thresholds:

| Vital | Window | Threshold |
| --- | --- | --- |
| Glucose / CGM | 30–180 min | 20 |
| Blood pressure | 30–240 min | 15 |
| Heart rate | 15–120 min | 20 |

The baseline is the mean of the last 5 same-type vitals before the meal. Possible contributing factors include meal carb load, diabetes context, medication timing, stress, and poor sleep. Output is always phrased as association, never causation.

---

## Database

PostgreSQL with SQLAlchemy 2.0 async. Engine: `pool_size=10`, `max_overflow=20`.

### Identity & Billing

`users` · `roles` · `user_roles` · `packages` · `subscriptions` · `payments` · `upload_limits` · `token_usage` · `audit_logs` · `password_resets`

### Patient & Clinical

`patient_pii` · `patient_persona` · `hipaa_audit_logs` · `medical_reports` · `medical_report_entities` · `medical_condition_snapshots` · `lab_results` · `medication_schedules`

### Timeline & Planning

`meal_events` · `meal_items` · `meal_media` · `vital_events` · `mood_checkins` · `correlation_insights` · `nutrition_targets` · `diet_plans` · `diet_plan_meals` · `daily_summaries`

### Recipes

`diet_profiles` · `generated_recipes` · `weekly_meal_schedules` · `recipe_tracking_entries`

The legacy `nutrition_data` and `report_data` blob tables were dropped in migration `8a44d0f5501f`.

---

## Security

### Password Handling

- **Argon2id** primary, bcrypt fallback. Hash format is detected on verification.
- Maximum 1024 UTF-8 bytes.
- Passwords over bcrypt's 72-byte limit are SHA-256 pre-hashed to avoid silent truncation.
- Minimum strength: **6 characters**.
- Password reset tokens are hashed before storage, expire after 1 hour, and are single-use.

### JWT

- `python-jose`, `HS256` by default.
- Typed claims: `type` is `access` or `refresh`; mismatches are rejected.
- Claims: `sub` (user UUID), `email`, `exp`, `type`.
- `ACCESS_TOKEN_EXPIRE_MINUTES` — `.env.example` sets 30; the in-code default is 43200. Set it explicitly.
- `REFRESH_TOKEN_EXPIRE_DAYS` — 7. The refresh endpoint issues a new access token only (no rotation).

### Encryption

AES-256-GCM over `patient_pii` (`full_name`, `email`, `phone_number`). The key comes from `ENCRYPTION_KEY` (base64, exactly 32 bytes); a fresh 12-byte nonce is generated per encryption.

### Dependencies

| Dependency | Behaviour |
| --- | --- |
| `get_current_user` | Verifies an access token; loads an active, non-deleted user. 401 otherwise. |
| `get_current_active_user` | Adds a 403 for inactive or deleted accounts. |
| `require_role([...])` | Role check via `roles` ← `user_roles`. 403 on mismatch. |
| `require_user` | `require_role(["user", "admin"])`. |
| `require_admin` | Compares the `X-Admin-Key` header against `ADMIN_KEY`; returns a mock system user. |

> `require_role` and `require_user` are implemented but **not currently attached to any route**. Admin access in practice is API-key based.

### Audit Trail

- `audit_logs` — authentication events, authorisation failures, data modifications.
- `hipaa_audit_logs` — `phi_access`, `phi_create`, `phi_update`, `phi_delete`, `phi_encrypt`, `phi_decrypt`, `phi_anonymize`, with IP address, user agent, and field-level detail.

### Rate Limiting

`RATE_LIMIT_LOGIN_ATTEMPTS` (5) and `RATE_LIMIT_LOGIN_WINDOW_MINUTES` (15) are defined in settings but **not enforced** — there is no throttling middleware or limiter dependency. Login attempts are not currently throttled.

---

## Subscriptions

| | Free | Paid |
| --- | --- | --- |
| Food uploads/day | 2 (`FREE_TIER_DAILY_UPLOAD_LIMIT`) | Unlimited |
| Nutrition queries/day | 2 (`FREE_TIER_DAILY_NUTRITION_LIMIT`) | Unlimited |
| Reports, timeline, plans, recipes | ✅ | ✅ |

- Signup grants a 7-day paid trial.
- Counters live in `upload_limits`, one row per user per day, resetting at midnight UTC.
- On expiry, admin-assigned packages auto-extend 30 days; otherwise the user is downgraded to `free`.
- Exceeding a quota returns `429`.

---

## Background Jobs

Two APScheduler cron jobs, both running hourly and then checking each user's local timezone (`patient_persona.timezone`).

| Job | Local trigger | Action |
| --- | --- | --- |
| `daily_summary_job` | 21:00, once per local date | Generates the daily summary. Skipped if one exists or data is insufficient. |
| `weekly_plan_refresh_job` | Monday 06:00 (`scheduled_weekly`), or an expired plan (`plan_expired`) | Generates a new 7-day plan and deactivates the previous one. |

> The scheduler is **disabled** — `start_scheduler()` is commented out in `src/presentation/api/routes.py`. Trigger the jobs manually via `POST /api/v1/admin/jobs/run-daily-summaries` and `POST /api/v1/admin/jobs/run-weekly-plan-refresh`.

---

## WebSocket / Socket.IO

`main.py` exports the Socket.IO ASGI app, so HTTP and the socket share one port (`/socket.io/`).

| Event | Direction | Payload |
| --- | --- | --- |
| `food_analysis_complete` | Server → client | Analysis result, broadcast globally. |

No `@sio.on(...)` handlers are registered — there is no inbound client channel.

> The emitting `socket_manager.sio` instance is currently separate from the mounted one in `routes.py`, so emissions may not reach clients as written.

RabbitMQ (`src/infrastructure/messaging/rabbitmq_client.py`) publishes to the durable `food_events` queue but is never consumed in production code, and no RabbitMQ service is defined in `docker-compose.yml`.

---

## Development

### Make Targets

```bash
make help              # list all targets

# Development
make dev               # hot-reload server on :8000
make serve             # production server
make restart

# Quality
make test              # pytest
make test-coverage     # pytest + coverage
make lint              # ruff check src/
make format            # ruff format src/
make format-check      # verify formatting
make validate          # format-check + lint + test + check-env

# Dependencies
make install           # uv sync
make upgrade           # uv sync --upgrade
make check-outdated    # uv tree --outdated

# Database
make setup-db
make full-setup        # setup-db + migrate + seed
make db-health
make check-env
make generate-key      # new AES-256-GCM key
make seed-data         # roles + packages

# Docker
make build
make run
make stop
make logs
make status
```

### Utility Scripts

| Script | Purpose |
| --- | --- |
| `scripts/generate_encryption_key.py` | Generate an `ENCRYPTION_KEY`. |
| `scripts/seed_roles.py` | Seed `user` and `admin` roles. |
| `scripts/seed_packages.py` | Seed subscription packages. |
| `scripts/check_packages.py` | Inspect package records. |
| `scripts/add_package_id.py` | Backfill `package_id` on subscriptions. |
| `scripts/get_debug_token.py` | Mint a debug token for local testing. |
| `scripts/setup_tables.sh` | Initial table setup. |
| `scripts/start_server.sh` / `stop_server.sh` | Service control. |
| `scripts/install_dependencies.sh` | Environment bootstrap. |
| `scripts/validate_service.sh` | Service health validation. |

---

## Migrations

```bash
make create-migration MSG="describe the change"
make migrate
make migration-history
make migration-current
make migration-heads
make force-migrate     # downgrade -1, then upgrade head
make reset-db          # WARNING: drops all data
make backup-db
make restore-db FILE=backup.sql
```

20 revisions, single head `1ea7e4b8e1b9` (`add_recipe`).

---

## Testing

```bash
uv run pytest test/ -v                                # explicit
uv run pytest test/ -v --cov=src --cov-report=html     # coverage
```

The suite lives in `backend/test/` and covers the Bedrock utilities, dashboard endpoints, the diet plan service, the health correlation graph, the health timeline service, mood check-in routes, nutrition metrics, the nutrition target service, and UUID-safe logging.

> **Note:** the `make test` and `make test-coverage` targets point at `tests/`, but the directory is named `test/`. Run pytest against `test/` directly, or fix the paths in `backend/Makefile`.

---

## Troubleshooting

### Database connection

```bash
docker compose ps postgres
docker compose logs postgres
pg_isready -h localhost -p 5437        # host port 5437 → container 5432
```

### Migrations

```bash
uv run alembic current
uv run alembic history
uv run alembic heads
uv run alembic upgrade head
```

Multiple heads mean an unmerged branch — `02c57b282908` is the historical merge revision.

### LLM / Bedrock

```bash
uv run python test_model.py     # prints the resolved provider and model
```

Check that both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set, that `ASIA…` keys include `AWS_SESSION_TOKEN`, and that `BEDROCK_MODEL_ID` is not still the `.env.example` placeholder.

### Auth

- `401` — missing/invalid access token, or a refresh token used as an access token.
- `403` — inactive or soft-deleted account.
- Admin `403` — `X-Admin-Key` does not match `ADMIN_KEY`.

### PDF / image uploads

- Max 5 MB per file.
- MIME: `image/jpeg`, `image/png`, `image/webp`.
- PDFs require Poppler. If missing, the API returns a 500 with a "Poppler is not installed" message.
- **Only the first page of a PDF is processed.**

---

## License

MIT — see [`../LICENSE`](../LICENSE).
