"""
Example Celery tasks for QuickRoute using the plugin system.

Demonstrates how to use Celery through the plugin interface.
"""

import time
import random
from datetime import datetime
from ..plugins.celery_plugin import CeleryPlugin
from ..database import AsyncSessionLocal
from ..models import User
from ..logging import logger
from sqlalchemy import select


def get_celery_plugin() -> CeleryPlugin:
    """Get the Celery plugin instance."""
    from ..plugins import get_plugin_manager
    from ..settings import settings
    manager = get_plugin_manager(settings)
    return manager.get_plugin('celery')


# Task decorators using plugin
def celery_task(name: str = None, bind: bool = False, **kwargs):
    """Decorator using Celery plugin."""
    plugin = get_celery_plugin()
    if plugin and plugin.enabled:
        return plugin.task(name=name, bind=bind, **kwargs)
    else:
        # Fallback decorator that executes immediately
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


def periodic_celery_task(schedule: str, name: str = None, **kwargs):
    """Decorator for periodic tasks using Celery plugin."""
    plugin = get_celery_plugin()
    if plugin and plugin.enabled:
        return plugin.periodic_task(schedule=schedule, name=name, **kwargs)
    else:
        # Fallback to built-in periodic jobs
        from ..jobs import periodic
        return periodic(schedule=schedule, name=name, **kwargs)


import functools


# Basic Celery task examples
@celery_task(name="send_welcome_email")
def send_welcome_email_task(user_id: int):
    """
    Send welcome email to new user.

    Example of a simple Celery task that could be called after user registration.
    """
    logger.info(f"Sending welcome email to user {user_id}")

    # Simulate email sending delay
    time.sleep(2)

    # In real implementation, this would send an actual email
    logger.info(f"Welcome email sent to user {user_id}")

    return {
        'status': 'sent',
        'user_id': user_id,
        'sent_at': datetime.utcnow().isoformat()
    }


@celery_task(bind=True, max_retries=3)
def send_notification_with_retry(self, user_id: int, message: str):
    """
    Send notification with retry logic.

    Demonstrates Celery's built-in retry mechanism.
    """
    try:
        logger.info(f"Sending notification to user {user_id}: {message}")

        # Simulate occasional failure (10% chance)
        if random.random() < 0.1:
            raise Exception("Simulated notification service failure")

        # Simulate API call
        time.sleep(1)

        logger.info(f"Notification sent to user {user_id}")
        return {
            'status': 'sent',
            'user_id': user_id,
            'message': message,
            'sent_at': datetime.utcnow().isoformat()
        }

    except Exception as exc:
        logger.warning(f"Notification failed, retrying: {exc}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


# Heavy computation tasks
@celery_task(name="process_user_analytics")
def process_user_analytics_task(user_id: int):
    """
    Process heavy analytics for a user.

    Example of CPU-intensive task that should run in background.
    """
    logger.info(f"Processing analytics for user {user_id}")

    # Simulate heavy computation
    time.sleep(5)

    # Simulate analytics calculation
    analytics = {
        'user_id': user_id,
        'activity_score': random.randint(1, 100),
        'engagement_rate': round(random.uniform(0.1, 1.0), 2),
        'recommendations': [f"item_{i}" for i in range(random.randint(1, 5))],
        'processed_at': datetime.utcnow().isoformat()
    }

    logger.info(f"Analytics processed for user {user_id}")
    return analytics


@celery_task(name="generate_monthly_report")
def generate_monthly_report_task():
    """
    Generate monthly system report.

    Example of long-running task that generates reports.
    """
    logger.info("Starting monthly report generation")

    # Simulate report generation with multiple steps
    steps = [
        "Gathering user statistics",
        "Analyzing usage patterns",
        "Calculating metrics",
        "Generating charts",
        "Compiling report"
    ]

    for i, step in enumerate(steps):
        logger.info(f"Step {i+1}/{len(steps)}: {step}")
        time.sleep(2)  # Simulate processing time

    report = {
        'month': datetime.utcnow().strftime('%Y-%m'),
        'total_users': 150,
        'active_users': 120,
        'new_signups': 25,
        'generated_at': datetime.utcnow().isoformat(),
        'processing_time_seconds': len(steps) * 2
    }

    logger.info("Monthly report generated successfully")
    return report


# Hybrid periodic tasks (both built-in and Celery)
@periodic_celery_task("every 10 minutes", name="sync_external_data")
def sync_external_data():
    """
    Sync data with external APIs.

    This task runs every 10 minutes via built-in scheduler for reliability,
    but can also be triggered via Celery for distributed execution.
    """
    logger.info("Starting external data sync")

    # Simulate API calls
    external_apis = ['users', 'products', 'orders']
    results = {}

    for api in external_apis:
        logger.info(f"Syncing {api} data")
        time.sleep(1)  # Simulate API call

        # Simulate fetched data
        results[api] = {
            'items': random.randint(10, 100),
            'updated_at': datetime.utcnow().isoformat()
        }

    logger.info(f"External data sync completed: {results}")
    return results


@periodic_celery_task("daily", name="cleanup_old_sessions_celery")
def cleanup_old_sessions():
    """
    Clean up old user sessions.

    Runs daily via built-in scheduler, but can be distributed via Celery.
    """
    logger.info("Starting session cleanup")

    # This is a placeholder - in real implementation,
    # you would clean up session storage (Redis, database, etc.)
    time.sleep(2)

    cleaned_count = random.randint(50, 200)
    logger.info(f"Cleaned up {cleaned_count} old sessions")

    return {
        'cleaned_sessions': cleaned_count,
        'cleaned_at': datetime.utcnow().isoformat()
    }


# Async database operations
@celery_task(name="update_user_statistics")
def update_user_statistics():
    """
    Update user statistics in database.

    Demonstrates database operations in Celery tasks.
    """
    import asyncio
    from ..database import AsyncSessionLocal
    from sqlalchemy import select, func

    async def update_stats():
        async with AsyncSessionLocal() as session:
            total_users = await session.scalar(select(func.count(User.id)))
            active_users = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )

            # In real implementation, you would update a statistics table
            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'updated_at': datetime.utcnow().isoformat()
            }

            logger.info(f"User statistics updated: {stats}")
            return stats

    return asyncio.run(update_stats())


# Example of using plugin's execute method in async context
async def example_async_celery_usage():
    """
    Example showing how to use Celery plugin execute method within async functions.
    """
    plugin = get_celery_plugin()
    if not plugin or not plugin.enabled:
        logger.warning("Celery plugin not available")
        return None

    try:
        result = await plugin.execute(
            process_user_analytics_task,
            user_id=123
        )
        logger.info(f"Analytics result: {result}")

        import asyncio
        tasks = [
            plugin.execute(send_welcome_email_task, user_id=1),
            plugin.execute(send_welcome_email_task, user_id=2),
            plugin.execute(process_user_analytics_task, user_id=123)
        ]

        results = await asyncio.gather(*tasks)
        logger.info(f"Concurrent task results: {results}")

        return results

    except Exception as e:
        logger.error(f"Error in async Celery usage: {e}")
        raise


# Email sending task with template
@celery_task(name="send_templated_email")
def send_templated_email_task(email_to: str, template_name: str, context: dict):
    """
    Send templated email using Celery plugin.

    Args:
        email_to: Recipient email address
        template_name: Name of the email template
        context: Template context variables
    """
    logger.info(f"Sending templated email '{template_name}' to {email_to}")

    # Simulate template rendering and email sending
    time.sleep(3)

    result = {
        'email_to': email_to,
        'template_name': template_name,
        'context_keys': list(context.keys()),
        'sent_at': datetime.utcnow().isoformat(),
        'status': 'sent'
    }

    logger.info(f"Templated email sent: {result}")
    return result


# File processing task
@celery_task(name="process_uploaded_file")
def process_uploaded_file_task(file_path: str, processing_options: dict):
    """
    Process uploaded file in background using Celery plugin.

    Args:
        file_path: Path to the uploaded file
        processing_options: Processing configuration
    """
    logger.info(f"Processing file: {file_path}")

    # Simulate file processing steps
    steps = ['validating', 'parsing', 'transforming', 'storing']

    for step in steps:
        logger.info(f"File processing step: {step}")
        time.sleep(2)

    result = {
        'file_path': file_path,
        'processing_options': processing_options,
        'status': 'completed',
        'processed_at': datetime.utcnow().isoformat(),
        'file_size': random.randint(1024, 10240)
    }

    logger.info(f"File processing completed: {result}")
    return result


# Utility functions for plugin interaction
def get_celery_status():
    """Get Celery plugin status."""
    plugin = get_celery_plugin()
    if plugin:
        return plugin.get_status()
    return {'celery_available': False, 'message': 'Celery plugin not found'}


def list_celery_tasks():
    """List all Celery tasks via plugin."""
    plugin = get_celery_plugin()
    if plugin and plugin.enabled:
        return plugin.list_tasks()
    return {}


def execute_celery_task(task_func, *args, **kwargs):
    """Execute Celery task with fallback."""
    plugin = get_celery_plugin()
    if plugin and plugin.enabled:
        return plugin.execute(task_func, *args, **kwargs)
    else:
        # Fallback execution
        return task_func(*args, **kwargs)