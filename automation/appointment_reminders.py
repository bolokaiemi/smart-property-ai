"""Placeholder appointment reminder automation module.
Provides a minimal job registration that logs execution.
Replace with real appointment reminder logic as needed.
"""

from __future__ import annotations
import logging
from automation.scheduler import AutomationScheduler, ScheduledJob

logger = logging.getLogger(__name__)

async def _appointment_reminder_placeholder() -> None:
    """Placeholder async job for appointment reminders.
    Currently just logs that it ran.
    """
    logger.info("[AppointmentReminder] Placeholder job executed")

def register_appointment_reminder_job(
    *,
    scheduler: AutomationScheduler,
    interval_seconds: float = 3600,
    run_immediately: bool = True,
    replace_existing: bool = False,
) -> ScheduledJob:
    """Register the appointment‑reminder job with the scheduler.
    Parameters are the same as in other automation modules.
    """
    return scheduler.register_job(
        name="appointment-reminders",
        callback=_appointment_reminder_placeholder,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
        description="Placeholder appointment reminder job.",
        replace_existing=replace_existing,
    )

__all__ = ["register_appointment_reminder_job"]
