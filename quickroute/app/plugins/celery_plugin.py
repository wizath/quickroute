"""
Celery plugin for QuickRoute.

Provides Celery integration through the plugin system.
"""

from typing import Any, Dict, Optional, Callable, Union
import asyncio
import inspect
from .base import BasePlugin
from ..logging import logger


class CeleryPlugin(BasePlugin):
    """
    Celery plugin for distributed task processing.

    Provides decorators and utilities for Celery integration with fallback
    to synchronous execution when Celery is not available.
    """

    @property
    def name(self) -> str:
        return "celery"

    @property
    def description(self) -> str:
        return "Distributed task processing with Celery"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.celery_app = None
        self._task_registry = {}
        self._fallback_registry = {}

    def is_available(self) -> bool:
        """Check if Celery dependencies are available."""
        try:
            import redis
            from celery import Celery

            broker_url = getattr(self.settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
            if 'redis://' in broker_url:
                host, port, db = broker_url.replace('redis://', '').split(':')
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

            self.celery_app = Celery('fastdjango')

            self.celery_app.conf.update(
                broker_url=getattr(self.settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
                result_backend=getattr(self.settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
                task_serializer='json',
                accept_content=['json'],
                result_serializer='json',
                timezone='UTC',
                enable_utc=True,
                task_default_expires=3600,
                task_reject_on_worker_lost=True,
                task_track_started=True,
                result_expires=3600,
                worker_prefetch_multiplier=getattr(self.settings, 'CELERY_WORKER_PREFETCH_MULTIPLIER', 1),
                task_acks_late=getattr(self.settings, 'CELERY_TASK_ACKS_LATE', True),
            )

            # Auto-discover tasks
            self.celery_app.autodiscover_tasks(['app.celery'])

            self.initialized = True
            logger.info("Celery plugin initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Celery plugin: {e}")
            return False

    def shutdown(self):
        """Shutdown Celery plugin."""
        if self.celery_app:
            # Close connections if needed
            logger.info("Celery plugin shutdown")

    def task(self, name: Optional[str] = None, bind: bool = False, **kwargs):
        """
        Decorator for registering Celery tasks.

        Falls back to synchronous execution if Celery is not available.
        """
        def decorator(func: Callable) -> Callable:
            task_name = name or f"app.celery.tasks.{func.__name__}"

            self._fallback_registry[task_name] = func

            if self.initialized and self.celery_app:
                task = self.celery_app.task(
                    name=task_name,
                    bind=bind,
                    **kwargs
                )(func)

                task._fallback_func = func
                self._task_registry[task_name] = task
                return task
            else:
                # Fallback: return a mock task that executes synchronously
                @wraps(func)
                def fallback_task(*args, **kwargs):
                    if inspect.iscoroutinefunction(func):
                        return asyncio.run(func(*args, **kwargs))
                    else:
                        return func(*args, **kwargs)

                fallback_task.delay = lambda *args, **kwargs: fallback_task(*args, **kwargs)
                fallback_task.apply_async = lambda args=None, kwargs=None, **opts: fallback_task(*args, **kwargs)
                fallback_task.name = task_name
                fallback_task._fallback_func = func
                fallback_task._plugin = self

                self._task_registry[task_name] = fallback_task
                logger.debug(f"Created fallback task: {task_name}")
                return fallback_task

        return decorator

    def periodic_task(self, schedule: str, name: Optional[str] = None, **kwargs):
        """
        Decorator for periodic tasks that work with both built-in scheduler and Celery.
        """
        def decorator(func: Callable) -> Callable:
            from ..jobs import periodic as periodic_job
            periodic_job(schedule, name, **kwargs)(func)

            celery_name = name or func.__name__
            celery_task_name = f"app.celery.tasks.{celery_name}"

            celery_task_func = self.task(name=celery_task_name, **kwargs)(func)

            celery_task_func._periodic_schedule = schedule

            logger.info(f"Registered hybrid periodic task: {celery_task_name}")
            logger.info(f"  - Built-in scheduler: {schedule}")
            logger.info(f"  - Celery Beat: Available if enabled")

            return celery_task_func

        return decorator

    async def execute(self, task: Any, *args, **kwargs) -> Any:
        """
        Execute a Celery task and await its completion.

        This is the key function that allows async/await pattern with Celery.
        Blocks until the Celery task completes, making it behave like a regular async function.
        """
        if not self.initialized or not self.celery_app:
            # Fallback: execute directly
            if hasattr(task, '_fallback_func'):
                func = task._fallback_func
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            elif inspect.iscoroutinefunction(task):
                return await task(*args, **kwargs)
            else:
                return task(*args, **kwargs)

        try:
            # If task is already submitted (has .get() method)
            if hasattr(task, 'get'):
                # Task is already running, wait for completion
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, task.get)
                return result
            else:
                # Submit task and wait for completion
                task_result = task.delay(*args, **kwargs)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, task_result.get)
                return result

        except Exception as e:
            logger.error(f"Error executing Celery task: {e}")
            # Fallback to direct execution
            if hasattr(task, '_fallback_func'):
                func = task._fallback_func
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            raise

    def get_task_status(self, task_result: Any) -> dict:
        """Get status information for a Celery task."""
        if not self.initialized or not self.celery_app:
            return {
                'celery_available': False,
                'status': 'fallback_executed',
                'message': 'Celery not available, using fallback execution'
            }

        try:
            from celery.result import AsyncResult

            if isinstance(task_result, AsyncResult):
                return {
                    'celery_available': True,
                    'task_id': task_result.id,
                    'status': task_result.status,
                    'result': task_result.result if task_result.ready() else None,
                    'traceback': task_result.traceback if task_result.failed() else None,
                    'date_done': task_result.date_done,
                    'runtime': task_result.runtime,
                }
            else:
                return {
                    'celery_available': True,
                    'status': 'not_submitted',
                    'message': 'Task not yet submitted to Celery'
                }

        except Exception as e:
            logger.error(f"Error getting Celery task status: {e}")
            return {
                'celery_available': True,
                'status': 'error',
                'error': str(e)
            }

    def get_task(self, name: str) -> Optional[Any]:
        """Get registered task by name."""
        return self._task_registry.get(name)

    def list_tasks(self) -> Dict[str, Any]:
        """List all registered tasks."""
        if self.celery_app:
            return {name: task for name, task in self.celery_app.tasks.items()
                   if not name.startswith('celery.')}
        return self._task_registry

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive plugin status."""
        base_status = super().get_status()

        if self.initialized and self.celery_app:
            celery_status = {
                'broker_url': self.celery_app.conf.broker_url,
                'result_backend': self.celery_app.conf.result_backend,
                'registered_tasks': len(self.list_tasks()),
                'worker_concurrency': getattr(self.settings, 'CELERY_WORKER_CONCURRENCY', 4),
            }
            base_status.update(celery_status)

        return base_status


import functools
from functools import wraps