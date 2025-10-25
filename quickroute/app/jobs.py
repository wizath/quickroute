"""
Periodic job system for QuickRoute.

Decorator-based job registration with async execution support.
"""

import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
from .logging import logger
from .models import User
from .database import AsyncSessionLocal


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    """Result of a job execution."""
    status: JobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Any = None
    execution_time: Optional[float] = None


@dataclass
class Job:
    """Periodic job definition."""
    name: str
    func: Callable
    schedule: str  # Cron-like expression or interval
    enabled: bool = True
    max_retries: int = 3
    timeout: int = 300  # 5 minutes
    description: str = ""

    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    is_running: bool = False
    run_count: int = 0
    failure_count: int = 0
    last_result: Optional[JobResult] = None


class JobRegistry:
    """Registry for periodic jobs."""

    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.job_history: List[Dict[str, Any]] = []
        self.max_history = 1000

    def register(self, job: Job):
        """Register a new job."""
        if job.name in self.jobs:
            logger.warning(f"Job '{job.name}' already exists, overwriting")

        self.jobs[job.name] = job
        logger.info(f"Registered job: {job.name} (schedule: {job.schedule})")
        return job

    def get_job(self, name: str) -> Optional[Job]:
        """Get a job by name."""
        return self.jobs.get(name)

    def list_jobs(self) -> List[Job]:
        """List all registered jobs."""
        return list(self.jobs.values())

    def enable_job(self, name: str):
        """Enable a job."""
        if name in self.jobs:
            self.jobs[name].enabled = True
            logger.info(f"Enabled job: {name}")

    def disable_job(self, name: str):
        """Disable a job."""
        if name in self.jobs:
            self.jobs[name].enabled = False
            logger.info(f"Disabled job: {name}")

    def record_execution(self, job_name: str, result: JobResult):
        """Record a job execution result."""
        history_entry = {
            'job_name': job_name,
            'status': result.status.value,
            'started_at': result.started_at,
            'completed_at': result.completed_at,
            'error': result.error,
            'execution_time': result.execution_time,
            'timestamp': datetime.utcnow()
        }

        self.job_history.append(history_entry)

        if len(self.job_history) > self.max_history:
            self.job_history = self.job_history[-self.max_history:]

        if job_name in self.jobs:
            job = self.jobs[job_name]
            job.last_result = result
            job.last_run = result.completed_at
            job.run_count += 1

            if result.status == JobStatus.FAILED:
                job.failure_count += 1


# Global job registry
job_registry = JobRegistry()


def periodic(schedule: str, name: Optional[str] = None, **kwargs):
    """
    Decorator for registering periodic jobs.

    Args:
        schedule: Schedule expression (cron-like or interval)
        name: Job name (defaults to function name)
        **kwargs: Additional job configuration

    Examples:
        @periodic("*/5 * * * *")  # Every 5 minutes
        def cleanup_task():
            pass

        @periodic("daily", name="daily_report")
        def generate_report():
            pass

        @periodic("1h", max_retries=5)
        def process_queue():
            pass
    """
    def decorator(func: Callable) -> Callable:
        job_name = name or func.__name__

        job = Job(
            name=job_name,
            func=func,
            schedule=schedule,
            description=func.__doc__ or "",
            **kwargs
        )

        job_registry.register(job)
        return func

    return decorator


class JobScheduler:
    """Async job scheduler."""

    def __init__(self):
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the job scheduler."""
        if self.running:
            logger.warning("Job scheduler is already running")
            return

        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Job scheduler started")

    async def stop(self):
        """Stop the job scheduler."""
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Job scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Job scheduler loop started")

        while self.running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _check_and_run_jobs(self):
        """Check for jobs that need to run and execute them."""
        now = datetime.utcnow()

        for job in job_registry.list_jobs():
            if not job.enabled or job.is_running:
                continue

            if self._should_run_job(job, now):
                # Schedule job execution
                asyncio.create_task(self._run_job(job))

    def _should_run_job(self, job: Job, now: datetime) -> bool:
        """Check if a job should run now."""
        if job.next_run and job.next_run > now:
            return False

        if not job.last_run:
            return True

        return self._parse_schedule(job.schedule, job.last_run) <= now

    def _parse_schedule(self, schedule: str, last_run: datetime) -> datetime:
        """Parse schedule expression and return next run time."""
        # Simple schedule parsing for common patterns
        schedule = schedule.lower().strip()

        if schedule.startswith("every "):
            # "every 5 minutes", "every 1 hour", "every day"
            interval_str = schedule[6:]  # Remove "every "
            return self._parse_interval(interval_str, last_run)
        elif schedule in ["daily", "hourly", "weekly", "monthly"]:
            return self._parse_interval(schedule, last_run)
        elif schedule.endswith("m") or schedule.endswith("h") or schedule.endswith("d"):
            # "5m", "1h", "1d"
            return self._parse_interval(schedule, last_run)
        else:
            # Default to hourly if unrecognized
            return last_run + timedelta(hours=1)

    def _parse_interval(self, interval: str, last_run: datetime) -> datetime:
        """Parse interval string and return next run time."""
        interval = interval.lower().strip()

        if interval in ["daily"]:
            return last_run + timedelta(days=1)
        elif interval in ["hourly"]:
            return last_run + timedelta(hours=1)
        elif interval in ["weekly"]:
            return last_run + timedelta(weeks=1)
        elif interval in ["monthly"]:
            return last_run + timedelta(days=30)
        elif interval.endswith("minute") or interval.endswith("minutes"):
            minutes = int(interval.split()[0])
            return last_run + timedelta(minutes=minutes)
        elif interval.endswith("hour") or interval.endswith("hours"):
            hours = int(interval.split()[0])
            return last_run + timedelta(hours=hours)
        elif interval.endswith("day") or interval.endswith("days"):
            days = int(interval.split()[0])
            return last_run + timedelta(days=days)
        elif interval.endswith("m"):
            minutes = int(interval[:-1])
            return last_run + timedelta(minutes=minutes)
        elif interval.endswith("h"):
            hours = int(interval[:-1])
            return last_run + timedelta(hours=hours)
        elif interval.endswith("d"):
            days = int(interval[:-1])
            return last_run + timedelta(days=days)
        else:
            # Default to hourly
            return last_run + timedelta(hours=1)

    async def _run_job(self, job: Job):
        """Execute a single job."""
        job.is_running = True
        started_at = datetime.utcnow()

        result = JobResult(
            status=JobStatus.RUNNING,
            started_at=started_at
        )

        logger.info(f"Running job: {job.name}")

        try:
            if inspect.iscoroutinefunction(job.func):
                job_result = await asyncio.wait_for(
                    job.func(),
                    timeout=job.timeout
                )
            else:
                job_result = await asyncio.wait_for(
                    asyncio.to_thread(job.func),
                    timeout=job.timeout
                )

            completed_at = datetime.utcnow()
            execution_time = (completed_at - started_at).total_seconds()

            result = JobResult(
                status=JobStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                result=job_result,
                execution_time=execution_time
            )

            logger.info(f"Job '{job.name}' completed successfully in {execution_time:.2f}s")

        except asyncio.TimeoutError:
            completed_at = datetime.utcnow()
            result = JobResult(
                status=JobStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error="Job timed out"
            )
            logger.error(f"Job '{job.name}' timed out after {job.timeout} seconds")

        except Exception as e:
            completed_at = datetime.utcnow()
            result = JobResult(
                status=JobStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e)
            )
            logger.error(f"Job '{job.name}' failed: {e}")

        finally:
            job.is_running = False
            job_registry.record_execution(job.name, result)

            # Schedule next run
            job.next_run = self._parse_schedule(job.schedule, completed_at)

    async def run_job_now(self, job_name: str) -> JobResult:
        """Run a specific job immediately."""
        job = job_registry.get_job(job_name)
        if not job:
            raise ValueError(f"Job '{job_name}' not found")

        if job.is_running:
            raise RuntimeError(f"Job '{job_name}' is already running")

        logger.info(f"Running job '{job_name}' on demand")
        await self._run_job(job)

        return job.last_result

    def get_job_status(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get current status of a job."""
        job = job_registry.get_job(job_name)
        if not job:
            return None

        return {
            'name': job.name,
            'enabled': job.enabled,
            'is_running': job.is_running,
            'last_run': job.last_run.isoformat() if job.last_run else None,
            'next_run': job.next_run.isoformat() if job.next_run else None,
            'run_count': job.run_count,
            'failure_count': job.failure_count,
            'schedule': job.schedule,
            'last_result': {
                'status': job.last_result.status.value if job.last_result else None,
                'error': job.last_result.error,
                'execution_time': job.last_result.execution_time
            } if job.last_result else None
        }


# Global scheduler instance
job_scheduler = JobScheduler()