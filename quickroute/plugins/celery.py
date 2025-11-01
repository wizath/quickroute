"""
Celery plugin for QuickRoute.

Convention: exports 'Plugin' class.
"""

from quickroute.app.plugins.celery_plugin import CeleryPlugin

Plugin = CeleryPlugin

__all__ = ["Plugin", "CeleryPlugin"]
