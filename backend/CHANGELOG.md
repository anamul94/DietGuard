# Changelog

All notable changes to the DietGuard project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-04-27

### Added - Recipe Suggestion Feature

#### New Agents
- **`diet_chart_agent`** - AI agent that parses doctor's diet charts, prescriptions, and nutritionist recommendations to extract structured diet restrictions
- **`recipe_suggestion_agent`** - AI agent that generates personalized recipes based on diet restrictions, cuisine preferences, and calorie targets

#### New Database Tables
- `diet_profiles` - Stores user's extracted diet restrictions and preferences
- `generated_recipes` - Stores AI-generated recipes with full details and nutrition
- `weekly_meal_schedules` - Stores weekly meal plans with recipe references
- `recipe_tracking_entries` - Links recipes to the existing meal tracker

#### New API Endpoints
- `POST /api/v1/health/recipes/diet-profiles/upload` - Upload diet chart for AI extraction
- `POST /api/v1/health/recipes/diet-profiles/manual` - Create diet profile manually
- `GET /api/v1/health/recipes/diet-profiles` - List all diet profiles
- `GET /api/v1/health/recipes/diet-profiles/active` - Get active diet profile
- `GET /api/v1/health/recipes/diet-profiles/{id}` - Get specific diet profile
- `PATCH /api/v1/health/recipes/diet-profiles/{id}` - Update/confirm diet profile
- `POST /api/v1/health/recipes/suggest` - Generate single on-demand recipe
- `POST /api/v1/health/recipes/generate-schedule` - Generate weekly meal schedule
- `GET /api/v1/health/recipes/schedules/current` - Get current weekly schedule
- `GET /api/v1/health/recipes` - Get recipe history/favorites
- `GET /api/v1/health/recipes/{id}` - Get recipe details
- `PATCH /api/v1/health/recipes/{id}/favorite` - Toggle recipe favorite status
- `POST /api/v1/health/recipes/{id}/track` - Add recipe to meal tracker

#### New Files
- `src/infrastructure/database/recipe_models.py` - SQLAlchemy models for recipe feature
- `src/presentation/schemas/recipe_schemas.py` - Pydantic schemas for API
- `src/infrastructure/agents/diet_chart_agent.py` - Diet chart parsing agent
- `src/infrastructure/agents/recipe_suggestion_agent.py` - Recipe generation agent
- `src/application/services/recipe_service.py` - Business logic service

#### Features
- Extract diet restrictions from uploaded documents (images, PDFs)
- Support for manual diet profile creation
- Cuisine preference selection (Indian, Italian, Chinese, Bengali, etc.)
- Diet type support (vegetarian, non-vegetarian, vegan)
- Allergy tracking and exclusion
- Disliked ingredients filtering
- Cooking time preferences
- AI-estimated nutrition per recipe
- Weekly meal schedule generation with 7-day plans
- Recipe favorites system
- Integration with existing meal tracker
- Calorie target calculation from NutritionTarget

### Changed
- Added `cuisine_preference` field to `PatientPersona` model
- Registered new agents in `bedrock_utils.py` `KNOWN_AGENT_NAMES`
- Updated `alembic/env.py` to include recipe models
- Fixed `create_migration.py` to accept message parameter from Makefile

### Configuration
- Added `DIET_CHART_AGENT_LLM_PROVIDER` and `DIET_CHART_AGENT_LLM_MODEL` environment variables
- Added `RECIPE_SUGGESTION_AGENT_LLM_PROVIDER` and `RECIPE_SUGGESTION_AGENT_LLM_MODEL` environment variables

---

## [2.0.0] - Previous Release

### Core Features
- Medical Report Analysis
- Food Image Analysis  
- Nutritionist Recommendations
- QR Code Support for mobile uploads
- JWT Authentication
- Role-Based Access Control
- Subscription Management
- Health Timeline
- Daily Summaries
- Diet Plan Generation

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| Unreleased | 2026-04-27 | Recipe Suggestion Feature |
| 2.0.0 | - | Core platform with health timeline, meal tracking, vitals |
