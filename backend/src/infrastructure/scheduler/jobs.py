"""
Scheduled background jobs.

Design: jobs run every hour. Each run inspects every active user's current
local time and acts only when that user is inside the target time window.
This ensures a user in Kolkata gets their summary at 21:00 IST, not at
21:00 UTC (which would be 02:30 AM for them).

Jobs:
  - daily_summary_job   → triggers at 21:00–21:59 local time, once per day
  - weekly_plan_refresh → triggers Monday 06:00–06:59 local time, once per week
"""

from __future__ import annotations

import zoneinfo
from datetime import datetime, date
from typing import Tuple
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy import select

from ..database.database import AsyncSessionLocal
from ..database.patient_models import PatientPersona
from ..database.health_models import DietPlan
from ..utils.logger import logger
from ...application.services.daily_summary_service import DailySummaryService
from ...application.services.diet_plan_service import DietPlanService


# ─── Timezone helper ──────────────────────────────────────────────────────────

def _user_local_now(tz_str: str | None) -> datetime:
    """Return the current datetime in the user's timezone. Falls back to UTC."""
    try:
        tz = zoneinfo.ZoneInfo(tz_str or "UTC")
    except (ZoneInfoNotFoundError, KeyError):
        tz = zoneinfo.ZoneInfo("UTC")
    return datetime.now(tz)


# ─── Daily summary job ────────────────────────────────────────────────────────

async def daily_summary_job() -> None:
    """
    Runs every hour.
    For each user whose local time is currently 21:xx (9 PM),
    generate a daily summary for today (their local date) if one
    doesn't already exist.
    """
    logger.info("Scheduler: daily_summary_job started")
    triggered = 0
    skipped = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PatientPersona.user_id, PatientPersona.timezone)
        )
        rows = result.all()

    for user_id, tz_str in rows:
        local_now = _user_local_now(tz_str)
        if local_now.hour != 21:
            skipped += 1
            continue

        local_date = local_now.date()
        try:
            async with AsyncSessionLocal() as db:
                summary = await DailySummaryService.generate_summary(db, user_id, local_date)
            if summary:
                triggered += 1
                logger.info(
                    "Scheduler: daily summary generated",
                    user_id=str(user_id),
                    date=local_date.isoformat(),
                    timezone=tz_str,
                )
            else:
                skipped += 1  # Not enough data or already exists
        except Exception as exc:
            errors += 1
            logger.error(
                "Scheduler: daily summary failed",
                user_id=str(user_id),
                date=local_date.isoformat(),
                error=str(exc),
            )

    logger.info(
        "Scheduler: daily_summary_job finished",
        triggered=triggered,
        skipped=skipped,
        errors=errors,
    )


# ─── Weekly plan refresh job ──────────────────────────────────────────────────

async def weekly_plan_refresh_job() -> None:
    """
    Runs every hour.
    For each user whose local time is currently Monday 06:xx,
    regenerate their diet plan with trigger="scheduled_weekly".

    Also catches any user whose current active plan has expired
    (valid_until < today in their local timezone) regardless of day,
    and regenerates it.
    """
    logger.info("Scheduler: weekly_plan_refresh_job started")
    triggered = 0
    skipped = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        persona_result = await db.execute(
            select(PatientPersona.user_id, PatientPersona.timezone)
        )
        personas = persona_result.all()

    for user_id, tz_str in personas:
        local_now = _user_local_now(tz_str)
        local_date = local_now.date()

        is_monday_morning = (local_now.weekday() == 0 and local_now.hour == 6)

        # Also regenerate if plan is expired regardless of day
        plan_expired = False
        try:
            async with AsyncSessionLocal() as db:
                plan_row = await db.execute(
                    select(DietPlan.valid_until)
                    .where(DietPlan.user_id == user_id, DietPlan.is_active.is_(True))
                    .order_by(DietPlan.created_at.desc())
                    .limit(1)
                )
                valid_until = plan_row.scalar_one_or_none()
                if valid_until and valid_until < local_date:
                    plan_expired = True
        except Exception:
            pass

        if not is_monday_morning and not plan_expired:
            skipped += 1
            continue

        trigger = "scheduled_weekly" if is_monday_morning else "plan_expired"
        try:
            async with AsyncSessionLocal() as db:
                await DietPlanService.generate_diet_plan(db, user_id, trigger=trigger)
            triggered += 1
            logger.info(
                "Scheduler: diet plan refreshed",
                user_id=str(user_id),
                trigger=trigger,
                timezone=tz_str,
                local_day=local_now.strftime("%A"),
            )
        except Exception as exc:
            errors += 1
            logger.error(
                "Scheduler: diet plan refresh failed",
                user_id=str(user_id),
                trigger=trigger,
                error=str(exc),
            )

    logger.info(
        "Scheduler: weekly_plan_refresh_job finished",
        triggered=triggered,
        skipped=skipped,
        errors=errors,
    )
