"""
Celery plugin for QuickRoute.

Provides Celery integration through the plugin system.
"""

from typing import Any, Dict, Optional, Callable
import asyncio
from .base import BasePlugin
from quickroute.logging import logger
from quickroute.app.exceptions import QuickRouteException


class CeleryUnavailableError(QuickRouteException):
    """Raised when Celery is required but not available."""

    status_code = 503
    detail = "Celery is not available"


class CeleryPlugin(BasePlugin):
    """
    Celery plugin for distributed task processing.

    Provides decorators and utilities for Celery integration.
    Raises CeleryUnavailableError when Celery is not available.
    """

    name = "celery"
    version = "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.celery_app = None
        self._task_registry = {}

    def is_available(self) -> bool:
        """Check if Celery dependencies are available."""
        try:
            import redis

            broker_url = getattr(self.settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
            if "redis://" in broker_url:
                host, port, db = broker_url.replace("redis://", "").split(":")
                r = redis.Redis(host=host, port=int(port), db=int(db), socket_connect_timeout=2)
                r.ping()
                return True
        except Exception as e:
            logger.debug(f"Celery not available: {e}")
            return False
        return False

    def initialize(self) -> bool:
        """Initialize Celery application."""
        try:
            from celery import Celery

            self.celery_app = Celery("fastdjango")

            self.celery_app.conf.update(
                broker_url=getattr(self.settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
                result_backend=getattr(
                    self.settings, "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
                ),
                task_serializer="json",
                accept_content=["json"],
                result_serializer="json",
                timezone="UTC",
                enable_utc=True,
                task_default_expires=3600,
                task_reject_on_worker_lost=True,
                task_track_started=True,
                result_expires=3600,
                worker_prefetch_multiplier=getattr(
                    self.settings, "CELERY_WORKER_PREFETCH_MULTIPLIER", 1
                ),
                task_acks_late=getattr(self.settings, "CELERY_TASK_ACKS_LATE", True),
            )

            # Auto-discover tasks
            self.celery_app.autodiscover_tasks(["app.celery"])

            self.initialized = True
            logger.info("Celery plugin initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Celery plugin: {e}")
            return False

    def shutdown(self):
        """Shutdown Celery plugin."""
        if self.celery_app:
            logger.info("Celery plugin shutdown")

    def task(self, name: Optional[str] = None, bind: bool = False, **kwargs):
        """
        Decorator for registering Celery tasks.

        Raises CeleryUnavailableError if Celery is not available.
        """

        def decorator(func: Callable) -> Callable:
            task_name = name or f"app.celery.tasks.{func.__name__}"

            if not self.initialized or not self.celery_app:
                raise CeleryUnavailableError(
                    f"Cannot register task '{task_name}': Celery is not available"
                )

            task = self.celery_app.task(name=task_name, bind=bind, **kwargs)(func)
            self._task_registry[task_name] = task
            return task

        return decorator

    def periodic_task(self, schedule: str, name: Optional[str] = None, **kwargs):
        """
        Decorator for periodic tasks that work with both built-in scheduler and Celery.
        """

        def decorator(func: Callable) -> Callable:
            from quickroute.app.jobs import periodic as periodic_job

            periodic_job(schedule, name, **kwargs)(func)

            celery_name = name or func.__name__
            celery_task_name = f"app.celery.tasks.{celery_name}"

            celery_task_func = self.task(name=celery_task_name, **kwargs)(func)

            celery_task_func._periodic_schedule = schedule

            logger.info(f"Registered hybrid periodic task: {celery_task_name}")
            logger.info(f"  - Built-in scheduler: {schedule}")
            logger.info("  - Celery Beat: Available if enabled")

            return celery_task_func

        return decorator

    async def execute(self, task: Any, *args, **kwargs) -> Any:
        """
        Execute a Celery task and await its completion.

        This is the key function that allows async/await pattern with Celery.
        Blocks until the Celery task completes, making it behave like a regular async function.

        Raises CeleryUnavailableError if Celery is not available.
        """
        if not self.initialized or not self.celery_app:
            raise CeleryUnavailableError("Cannot execute task: Celery is not available")

        # If task is already submitted (has .get() method)
        if hasattr(task, "get"):
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, task.get)
            return result
        else:
            # Submit task and wait for completion
            task_result = task.delay(*args, **kwargs)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, task_result.get)
            return result

    def get_task_status(self, task_result: Any) -> dict:
        """Get status information for a Celery task."""
        if not self.initialized or not self.celery_app:
            raise CeleryUnavailableError("Cannot get task status: Celery is not available")

        from celery.result import AsyncResult

        if isinstance(task_result, AsyncResult):
            return {
                "task_id": task_result.id,
                "status": task_result.status,
                "result": task_result.result if task_result.ready() else None,
                "traceback": task_result.traceback if task_result.failed() else None,
                "date_done": task_result.date_done,
                "runtime": task_result.runtime,
            }
        else:
            return {
                "status": "not_submitted",
                "message": "Task not yet submitted to Celery",
            }

    def get_task(self, name: str) -> Optional[Any]:
        """Get registered task by name."""
        return self._task_registry.get(name)

    def list_tasks(self) -> Dict[str, Any]:
        """List all registered tasks."""
        if self.celery_app:
            return {
                name: task
                for name, task in self.celery_app.tasks.items()
                if not name.startswith("celery.")
            }
        return self._task_registry


# Export for plugin discovery
Plugin = CeleryPlugin

__all__ = ["Plugin", "CeleryPlugin", "CeleryUnavailableError"]
