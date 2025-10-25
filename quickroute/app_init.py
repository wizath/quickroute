"""
QuickRoute app initialization.

This file handles the setup and initialization of a QuickRoute application.
"""

from fastapi import FastAPI
from . import app as app_module
from .settings import settings


def create_app() -> FastAPI:
    """Create and configure a QuickRoute application."""

    return app_module.app


def get_settings():
    """Get the application settings."""
    return settings


def get_user_model():
    """Get the User model."""
    return app_module.User


def get_database_session():
    """Get the database session."""
    return app_module.AsyncSessionLocal


# Convenience exports
__all__ = [
    "create_app",
    "get_settings",
    "get_user_model",
    "get_database_session"
]