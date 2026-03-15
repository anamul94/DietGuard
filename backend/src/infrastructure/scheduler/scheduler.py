"""
APScheduler setup.

Two jobs:
  - daily_summary_job      : every hour at :00, checks who is at 21:xx local
  - weekly_plan_refresh_job: every hour at :30, checks who is at Mon 06:xx local
                             and also catches expired plans
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..utils.logger import logger
from .jobs import daily_summary_job, weekly_plan_refresh_job

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    scheduler.add_job(
        daily_summary_job,
        trigger=CronTrigger(minute=0),   # top of every hour
        id="daily_summary",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        weekly_plan_refresh_job,
        trigger=CronTrigger(minute=30),  # :30 of every hour
        id="weekly_plan_refresh",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info("Scheduler started", jobs=[job.id for job in scheduler.get_jobs()])


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
