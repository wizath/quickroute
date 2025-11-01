"""
Celery plugin for QuickRoute.

Re-exports CeleryPlugin from internal implementation.
"""

from ..app.plugins.celery_plugin import CeleryPlugin

__all__ = ['CeleryPlugin']
