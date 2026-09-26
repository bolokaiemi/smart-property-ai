"""Automation package providing a lightweight async scheduler.

This implementation is deliberately minimal – it only needs to be importable
by the FastAPI app and allow registration of jobs via ``register_job``.
Real background execution can be added later.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger("smart_property_ai.automation.scheduler")


@dataclass
class ScheduledJob:
    """Metadata for a job registered with :class:`AutomationScheduler`."""

    name: str
    callback: Callable[[], Awaitable[Any]]
    interval_seconds: float
    run_immediately: bool = True
    description: str = ""
    replace_existing: bool = False
    _task: Optional[asyncio.Task] = field(default=None, init=False, repr=False)

    async def _run_periodic(self) -> None:
        """Execute the callback repeatedly according to ``interval_seconds``.

        The first run respects ``run_immediately``. Subsequent runs wait for the
        configured interval.
        """
        if self.run_immediately:
            await self._execute()
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self._execute()

    async def _execute(self) -> None:
        try:
            logger.debug("Running scheduled job %s", self.name)
            await self.callback()
        except Exception:  # pragma: no cover – placeholder, keep robust
            logger.exception("Error while executing job %s", self.name)

    def start(self) -> None:
        """Create and store the asyncio task that drives the job.
        Called by :class:`AutomationScheduler` when the scheduler starts.
        """
        if self._task is None:
            self._task = asyncio.create_task(self._run_periodic())
            logger.debug("Started asyncio task for job %s", self.name)

    async def stop(self) -> None:
        """Cancel the underlying asyncio task, if any."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.debug("Stopped job %s", self.name)
            self._task = None


class AutomationScheduler:
    """Very small scheduler used by the FastAPI ``lifespan`` manager.

    It stores ``ScheduledJob`` objects and can start/stop them in bulk.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        logger.debug("AutomationScheduler instantiated")

    def register_job(
        self,
        *,
        name: str,
        callback: Callable[[], Awaitable[Any]],
        interval_seconds: float,
        run_immediately: bool = True,
        enabled: bool = True,
        description: str = "",
        replace_existing: bool = False,
    ) -> ScheduledJob:
        """Register a job and optionally replace an existing one.

        Parameters
        ----------
        name: str
            Unique identifier for the job.
        callback: Callable[[], Awaitable[Any]]
            Async function that performs the job's work.
        interval_seconds: float
            How often to run the job.
        run_immediately: bool, optional
            Execute the job as soon as the scheduler starts.
        enabled: bool, optional
            If ``False`` the job is stored but not started.
        description: str, optional
            Human‑readable description for logging/monitoring.
        replace_existing: bool, optional
            Overwrite an existing job with the same name.
        """
        if name in self._jobs and not replace_existing:
            raise ValueError(f"Job '{name}' already registered")
        job = ScheduledJob(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            run_immediately=run_immediately,
            description=description,
            replace_existing=replace_existing,
        )
        self._jobs[name] = job
        logger.debug(
            "Registered job %s (interval=%.1fs, enabled=%s)",
            name,
            interval_seconds,
            enabled,
        )
        if enabled:
            job.start()
        return job

    async def start(self) -> None:
        """Start all registered jobs that are currently disabled.
        In this simple implementation jobs are started at registration time,
        so this method merely logs that the scheduler is active.
        """
        logger.info("AutomationScheduler started with %d jobs", len(self._jobs))
        # Ensure any jobs that were registered with ``enabled=False`` are started now.
        for job in self._jobs.values():
            if job._task is None:
                job.start()

    async def stop(self) -> None:
        """Stop every scheduled job gracefully."""
        logger.info("AutomationScheduler stopping %d jobs", len(self._jobs))
        await asyncio.gather(*(job.stop() for job in self._jobs.values()))
        self._jobs.clear()

__all__ = ["AutomationScheduler", "ScheduledJob"]
