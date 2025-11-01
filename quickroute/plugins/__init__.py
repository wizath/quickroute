"""
QuickRoute plugins package.

Re-exports plugins from internal app.plugins for clean public API.
"""

from ..app.plugins.base import BasePlugin, PluginManager, get_plugin_manager

__all__ = [
    'BasePlugin',
    'PluginManager',
    'get_plugin_manager',
]
