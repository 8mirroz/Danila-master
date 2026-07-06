"""
PartsOps AI Manager v3 — Scheduler
Контракт: 04_BACKEND_CONTRACTS/scheduler.py
Лёгкий планировщик задач на threading.Timer (APScheduler fallback).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Dict, List
from datetime import datetime, timezone
import uuid


class ScheduledJob:
    """Описание запланированной задачи."""
    def __init__(
        self,
        func: Callable,
        interval_seconds: int,
        job_id: Optional[str] = None,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
    ):
        self.id = job_id or str(uuid.uuid4())[:8]
        self.func = func
        self.interval = interval_seconds
        self.args = args or ()
        self.kwargs = kwargs or {}
        self._timer: Optional[threading.Timer] = None
        self.running = False
        self._cancelled = False

    def _run(self) -> None:
        if self._cancelled:
            return
        try:
            self.func(*self.args, **self.kwargs)
        finally:
            if not self._cancelled:
                self._schedule_next()

    def _schedule_next(self) -> None:
        self._timer = threading.Timer(self.interval, self._run)
        self._timer.daemon = True
        self._timer.start()

    def start(self) -> None:
        if not self.running:
            self._cancelled = False
            self.running = True
            self._schedule_next()

    def stop(self) -> None:
        if self._timer:
            self._cancelled = True
            self._timer.cancel()
        self.running = False


class Scheduler:
    """
    Планировщик фоновых задач (seed, cleanup, metrics).
    Использует threading.Timer вместо APScheduler для лёгкости.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}

    def every(
        self,
        seconds: int,
        func: Callable,
        job_id: Optional[str] = None,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        start: bool = True,
    ) -> ScheduledJob:
        """
        Запланировать функцию на выполнение каждые N секунд.
        """
        job = ScheduledJob(
            func=func,
            interval_seconds=seconds,
            job_id=job_id,
            args=args,
            kwargs=kwargs,
        )
        self._jobs[job.id] = job
        if start:
            job.start()
        return job

    def run_once(
        self,
        seconds: int,
        func: Callable,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
    ) -> ScheduledJob:
        """Запланировать одноразовое выполнение."""
        job = ScheduledJob(
            func=func,
            interval_seconds=seconds,
            job_id=f"once_{int(time.time())}_{uuid.uuid4().hex[:4]}",
            args=args,
            kwargs=kwargs,
        )
        self._jobs[job.id] = job
        job.start()
        return job

    def cancel(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].stop()
            del self._jobs[job_id]
            return True
        return False

    def list_jobs(self) -> List[Dict]:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        return [
            {
                "job_id": j.id,
                "interval": j.interval,
                "running": j.running,
                "created_at": now,
            }
            for j in self._jobs.values()
        ]

    def shutdown(self) -> None:
        for job in self._jobs.values():
            job.stop()
        self._jobs.clear()


# Singleton-глобальный планировщик
scheduler = Scheduler()
