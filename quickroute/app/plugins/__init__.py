"""
Plugin system for QuickRoute.

Plugins are loaded automatically from INSTALLED_PLUGINS setting.
"""

from .base import BasePlugin, PluginManager, get_plugin_manager
from .celery_plugin import CeleryPlugin

__all__ = [
    'BasePlugin',
    'PluginManager',
    'get_plugin_manager',
    'CeleryPlugin',
]