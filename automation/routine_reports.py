"""Placeholder routine report automation module.
Provides a minimal job registration that logs execution.
Replace with real report generation logic as needed.
"""

from __future__ import annotations
import logging
from automation.scheduler import AutomationScheduler, ScheduledJob

logger = logging.getLogger(__name__)

async def _routine_report_placeholder() -> None:
    """Placeholder async job for routine reports.
    Currently just logs that it ran.
    """
    logger.info("[RoutineReport] Placeholder job executed")

def register_routine_report_job(
    *,
    scheduler: AutomationScheduler,
    interval_seconds: float = 86400 * 30,
    run_immediately: bool = True,
    replace_existing: bool = False,
) -> ScheduledJob:
    """Register the routine‑report job with the scheduler.
    Parameters are the same as in other automation modules.
    """
    return scheduler.register_job(
        name="routine-reports",
        callback=_routine_report_placeholder,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
        description="Placeholder routine report job.",
        replace_existing=replace_existing,
    )

__all__ = ["register_routine_report_job"]
