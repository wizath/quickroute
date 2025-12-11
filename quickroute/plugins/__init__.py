"""
QuickRoute plugins package.

Plugins are loaded automatically from INSTALLED_PLUGINS setting.
Each plugin module must export a 'Plugin' class.
"""

from .base import BasePlugin, PluginManager, get_plugin_manager

__all__ = [
    "BasePlugin",
    "PluginManager",
    "get_plugin_manager",
]
