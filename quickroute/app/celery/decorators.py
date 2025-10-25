"""
Celery task decorators for QuickRoute.

Provides hybrid decorators for both periodic jobs and Celery tasks.
"""

import asyncio
import inspect
from typing import Any, Callable, Optional, Union
from functools import wraps
from .app import celery_app, is_celery_available
from ..logging import logger


def celery_task(name: Optional[str] = None, bind: bool = False, **kwargs):
    """
    Decorator for registering Celery tasks.

    Falls back to async function execution if Celery is not available.

    Args:
        name: Task name (defaults to function name)
        bind: Whether to bind the task to self
        **kwargs: Additional Celery task options

    Examples:
        @celery_task
        def send_email_task(email, message):
            pass

        @celery_task(name="process_data", bind=True)
        def process_data_task(self, data):
            # Task with access to self (task instance)
            pass
    """
    def decorator(func: Callable) -> Callable:
        task_name = name or f"app.celery.tasks.{func.__name__}"

        original_func = func

        if is_celery_available():
            task = celery_app.task(
                name=task_name,
                bind=bind,
                **kwargs
            )(func)

            task._fallback_func = original_func
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
            fallback_task._fallback_func = original_func

            logger.warning(f"Celery not available, using fallback execution for task: {task_name}")
            return fallback_task

    return decorator


def periodic_celery_task(schedule: str, name: Optional[str] = None, **kwargs):
    """
    Decorator for registering periodic tasks with both built-in scheduler and Celery Beat.

    Creates both a built-in periodic job and a Celery task.
    The built-in job runs in-process, while Celery task can run in distributed workers.

    Args:
        schedule: Schedule expression (cron-like or interval)
        name: Task name (defaults to function name)
        **kwargs: Additional task options

    Examples:
        @periodic_celery_task("every 5 minutes")
        def cleanup_data():
            # Runs every 5 minutes via built-in scheduler
            # Can also be triggered via Celery
            pass
    """
    def decorator(func: Callable) -> Callable:
        from ..jobs import periodic as periodic_job
        periodic_job(schedule, name, **kwargs)(func)

        celery_name = name or func.__name__
        celery_task_name = f"app.celery.tasks.{celery_name}"

        celery_task_func = celery_task(name=celery_task_name, **kwargs)(func)

        celery_task_func._periodic_schedule = schedule

        logger.info(f"Registered hybrid periodic task: {celery_task_name}")
        logger.info(f"  - Built-in scheduler: {schedule}")
        logger.info(f"  - Celery Beat: Available if enabled")

        return celery_task_func

    return decorator


async def celery_execute(task: Any, *args, **kwargs) -> Any:
    """
    Execute a Celery task and await its completion.

    This is the key function that allows async/await pattern with Celery.
    Blocks until the Celery task completes, making it behave like a regular async function.

    Args:
        task: Celery task function
        *args: Task arguments
        **kwargs: Task keyword arguments

    Returns:
        Task result

    Examples:
        @celery_task
        def calculate_heavy_computation(x, y):
            # Heavy computation
            return x + y

        # In an async function:
        result = await celery_execute(calculate_heavy_computation, 5, 10)
        print(result)  # 15

        # Or using task name:
        from quickroute.app.celery.tasks import calculate_heavy_computation
        result = await celery_execute(calculate_heavy_computation.delay(5, 10))
    """
    if not is_celery_available():
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


def get_celery_task_status(task_result: Any) -> dict:
    """
    Get status information for a Celery task.

    Args:
        task_result: Celery AsyncResult or task function

    Returns:
        Dictionary with task status information
    """
    if not is_celery_available():
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