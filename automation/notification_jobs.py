"""Placeholder notification jobs automation module.
Provides a minimal job registration that logs execution.
Replace with real notification queue handling when ready.
"""

from __future__ import annotations
import logging
from automation.scheduler import AutomationScheduler, ScheduledJob

logger = logging.getLogger(__name__)

async def _notification_job_placeholder() -> None:
    """Placeholder async job for processing queued notifications.
    Currently just logs that it ran.
    """
    logger.info("[NotificationJob] Placeholder job executed")

def register_notification_job(
    *,
    scheduler: AutomationScheduler,
    interval_seconds: float = 300,  # every 5 minutes by default
    run_immediately: bool = True,
    replace_existing: bool = False,
) -> ScheduledJob:
    """Register the notification‑delivery job with the scheduler.
    Parameters follow the same pattern as the other automation modules.
    """
    return scheduler.register_job(
        name="notification-delivery",
        callback=_notification_job_placeholder,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
        description="Placeholder notification delivery job.",
        replace_existing=replace_existing,
    )

__all__ = ["register_notification_job"]
