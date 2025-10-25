"""
Example periodic jobs for QuickRoute.

These jobs demonstrate how to use the @periodic decorator for scheduled tasks.
"""

import asyncio
from datetime import datetime
from .jobs import periodic
from .models import User, BlacklistedToken
from .database import AsyncSessionLocal
from .logging import logger
from sqlalchemy import select, delete


@periodic("every 5 minutes", name="cleanup_expired_tokens")
async def cleanup_expired_tokens():
    """
    Clean up expired blacklisted tokens from database.

    Runs every 5 minutes to keep the token blacklist table clean.
    """
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()

        result = await session.execute(
            delete(BlacklistedToken).where(BlacklistedToken.expires_at < now)
        )
        await session.commit()

        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} expired blacklisted tokens")

        return {"deleted_tokens": deleted_count}


@periodic("hourly", name="user_statistics")
async def generate_user_statistics():
    """
    Generate user statistics for monitoring.

    Runs every hour to provide user count and activity statistics.
    """
    async with AsyncSessionLocal() as session:
        total_result = await session.execute(select(User))
        total_users = len(total_result.scalars().all())

        active_result = await session.execute(select(User).where(User.is_active == True))
        active_users = len(active_result.scalars().all())

        superuser_result = await session.execute(select(User).where(User.is_superuser == True))
        superusers = len(superuser_result.scalars().all())

        stats = {
            "total_users": total_users,
            "active_users": active_users,
            "superusers": superusers,
            "inactive_users": total_users - active_users,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"User statistics: {stats}")
        return stats


@periodic("daily", name="daily_health_check")
async def daily_health_check():
    """
    Perform daily health checks on the system.

    Runs once per day to verify system health and log any issues.
    """
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(User))
        health_status["checks"]["database"] = "OK"
    except Exception as e:
        health_status["checks"]["database"] = f"ERROR: {str(e)}"
        logger.error(f"Database health check failed: {e}")

    from .jobs import job_registry
    try:
        total_jobs = len(job_registry.list_jobs())
        enabled_jobs = len([j for j in job_registry.list_jobs() if j.enabled])
        health_status["checks"]["jobs"] = {
            "status": "OK",
            "total_jobs": total_jobs,
            "enabled_jobs": enabled_jobs
        }
    except Exception as e:
        health_status["checks"]["jobs"] = f"ERROR: {str(e)}"

    try:
        import psutil
        memory_info = psutil.virtual_memory()
        health_status["checks"]["memory"] = {
            "status": "OK",
            "used_percent": memory_info.percent,
            "available_gb": round(memory_info.available / (1024**3), 2)
        }

        if memory_info.percent > 90:
            health_status["checks"]["memory"]["status"] = "WARNING"
            logger.warning(f"High memory usage: {memory_info.percent}%")
    except ImportError:
        health_status["checks"]["memory"] = "SKIP (psutil not available)"
    except Exception as e:
        health_status["checks"]["memory"] = f"ERROR: {str(e)}"

    logger.info(f"Daily health check completed: {health_status}")
    return health_status


@periodic("10m", name="log_cleanup", max_retries=2)
async def cleanup_old_logs():
    """
    Clean up old log files and job history.

    Runs every 10 minutes to prevent log files from growing too large.
    """
    from .jobs import job_registry

    # Keep only last 100 job execution records
    original_max = job_registry.max_history
    job_registry.max_history = 100

    # Trim job history if needed
    if len(job_registry.job_history) > 100:
        removed_count = len(job_registry.job_history) - 100
        job_registry.job_history = job_registry.job_history[-100:]
        logger.info(f"Cleaned up {removed_count} old job history records")

    # Restore original max history
    job_registry.max_history = original_max

    return {"cleaned_records": removed_count if 'removed_count' in locals() else 0}


@periodic("weekly", name="database_maintenance")
async def database_maintenance():
    """
    Perform weekly database maintenance tasks.

    Runs once per week to optimize database performance.
    """
    maintenance_tasks = []

    # Analyze database (SQLite specific)
    try:
        async with AsyncSessionLocal() as session:
            # SQLite VACUUM to optimize database
            await session.execute("VACUUM")
            await session.commit()

        maintenance_tasks.append("Database VACUUM completed")
        logger.info("Database maintenance: VACUUM completed")
    except Exception as e:
        error_msg = f"Database VACUUM failed: {str(e)}"
        maintenance_tasks.append(error_msg)
        logger.error(error_msg)

    try:
        async with AsyncSessionLocal() as session:
            await session.execute("ANALYZE")
            await session.commit()

        maintenance_tasks.append("Database ANALYZE completed")
        logger.info("Database maintenance: ANALYZE completed")
    except Exception as e:
        error_msg = f"Database ANALYZE failed: {str(e)}"
        maintenance_tasks.append(error_msg)
        logger.error(error_msg)

    return {
        "tasks_completed": maintenance_tasks,
        "timestamp": datetime.utcnow().isoformat()
    }


@periodic("2h", name="cleanup_inactive_sessions", timeout=60)
async def cleanup_inactive_sessions():
    """
    Clean up inactive user sessions.

    Runs every 2 hours to remove expired session data.
    """
    # This is a placeholder - in a real implementation,
    # you would clean up session storage (Redis, database, etc.)

    # For now, we'll just log that this task ran
    logger.info("Session cleanup task completed")

    return {
        "message": "Session cleanup completed",
        "timestamp": datetime.utcnow().isoformat()
    }


# Example of a job that could send notifications
@periodic("daily", name="daily_report", enabled=False)
async def send_daily_report():
    """
    Send daily summary report (disabled by default).

    This would typically send an email or notification with daily statistics.
    """
    from .jobs import job_scheduler
    user_stats = await job_scheduler.run_job_now("user_statistics")

    # Format report
    report = f"""
    Daily Report - {datetime.utcnow().strftime('%Y-%m-%d')}

    User Statistics:
    - Total Users: {user_stats.result.get('total_users', 0)}
    - Active Users: {user_stats.result.get('active_users', 0)}
    - Superusers: {user_stats.result.get('superusers', 0)}

    Generated at: {datetime.utcnow().isoformat()}
    """

    logger.info(f"Daily report generated:\n{report}")

    return {"report_generated": True, "report": report}


# Example of a custom job with specific parameters
@periodic("30m", name="custom_task", max_retries=5, timeout=120)
async def custom_periodic_task():
    """
    Custom periodic task with custom configuration.

    Runs every 30 minutes with 5 retries and 2-minute timeout.
    """
    # This is where you'd implement your custom periodic logic
    # For example: data synchronization, cache warming, notifications, etc.

    await asyncio.sleep(2)  # Simulate some work

    return {"task_completed": True, "timestamp": datetime.utcnow().isoformat()}


# Job that demonstrates error handling
@periodic("15m", name="error_prone_job", max_retries=3)
async def error_prone_job():
    """
    Job that occasionally fails to demonstrate error handling.

    Runs every 15 minutes and has 3 retries on failure.
    """
    import random

    # Simulate occasional failure (10% chance)
    if random.random() < 0.1:
        raise Exception("Simulated job failure for testing")

    return {"success": True, "timestamp": datetime.utcnow().isoformat()}