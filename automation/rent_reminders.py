"""Placeholder rent reminder automation module.
Provides a minimal job registration that logs execution.
Replace with real business logic as needed.
"""

from __future__ import annotations
import logging
from automation.scheduler import AutomationScheduler, ScheduledJob

logger = logging.getLogger(__name__)

async def _rent_reminder_placeholder() -> None:
    """Placeholder async job for rent reminders.
    Currently just logs that it ran.
    """
    logger.info("[RentReminder] Placeholder job executed")

def register_rent_reminder_job(
    *,
    scheduler: AutomationScheduler,
    interval_seconds: float = 86400,
    run_immediately: bool = True,
    replace_existing: bool = False,
) -> ScheduledJob:
    """Register the rent‑reminder job with the scheduler.
    Parameters are the same as in other automation modules.
    """
    return scheduler.register_job(
        name="rent-reminders",
        callback=_rent_reminder_placeholder,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
        description="Placeholder rent reminder job.",
        replace_existing=replace_existing,
    )

__all__ = ["register_rent_reminder_job"]
