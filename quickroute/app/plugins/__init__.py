"""
Plugin system for QuickRoute.

Provides Flask-like extension system for adding optional functionality.
"""

from .base import BasePlugin, PluginManager, get_plugin_manager, register_plugin
from .celery_plugin import CeleryPlugin

# Built-in plugins registry
BUILTIN_PLUGINS = [
    CeleryPlugin,
]

def initialize_plugins(settings):
    """Initialize all built-in plugins."""
    manager = get_plugin_manager(settings)

    for plugin_class in BUILTIN_PLUGINS:
        plugin = plugin_class(settings)
        manager.register(plugin)

    manager.initialize_enabled_plugins()

    return manager

__all__ = [
    'BasePlugin',
    'PluginManager',
    'get_plugin_manager',
    'register_plugin',
    'initialize_plugins',
    'BUILTIN_PLUGINS',
    'CeleryPlugin'
]