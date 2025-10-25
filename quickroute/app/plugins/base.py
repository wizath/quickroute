"""
Base plugin system for QuickRoute.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from ..logging import logger


class BasePlugin(ABC):
    """
    Base class for all QuickRoute plugins.

    Plugins provide optional functionality that can be enabled/disabled
    without affecting core functionality.
    """

    def __init__(self, settings):
        self.settings = settings
        self.enabled = False
        self.initialized = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if plugin dependencies are available.

        Returns True if plugin can be initialized, False otherwise.
        """
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the plugin.

        Returns True if initialization successful, False otherwise.
        """
        pass

    @abstractmethod
    def shutdown(self):
        """Cleanup and shutdown the plugin."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get plugin status information.

        Returns:
            Dictionary with plugin status details.
        """
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'enabled': self.enabled,
            'initialized': self.initialized,
            'available': self.is_available(),
        }

    def enable(self) -> bool:
        """
        Enable the plugin.

        Returns True if enabled successfully, False otherwise.
        """
        if not self.is_available():
            logger.error(f"Cannot enable {self.name}: dependencies not available")
            return False

        try:
            if self.initialize():
                self.enabled = True
                logger.info(f"Plugin {self.name} enabled successfully")
                return True
            else:
                logger.error(f"Failed to initialize plugin {self.name}")
                return False
        except Exception as e:
            logger.error(f"Error enabling plugin {self.name}: {e}")
            return False

    def disable(self):
        """Disable the plugin."""
        if self.enabled:
            try:
                self.shutdown()
                self.enabled = False
                self.initialized = False
                logger.info(f"Plugin {self.name} disabled")
            except Exception as e:
                logger.error(f"Error disabling plugin {self.name}: {e}")

    def __str__(self):
        return f"{self.name} v{self.version} ({'enabled' if self.enabled else 'disabled'})"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PluginManager:
    """
    Manager for all QuickRoute plugins.
    """

    def __init__(self, settings):
        self.settings = settings
        self.plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin):
        """Register a plugin."""
        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin}")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get plugin by name."""
        return self.plugins.get(name)

    def list_plugins(self) -> List[BasePlugin]:
        """List all registered plugins."""
        return list(self.plugins.values())

    def enable_plugin(self, name: str) -> bool:
        """Enable a specific plugin."""
        plugin = self.get_plugin(name)
        if plugin:
            return plugin.enable()
        return False

    def disable_plugin(self, name: str):
        """Disable a specific plugin."""
        plugin = self.get_plugin(name)
        if plugin:
            plugin.disable()

    def get_available_plugins(self) -> List[BasePlugin]:
        """Get list of available plugins."""
        return [p for p in self.plugins.values() if p.is_available()]

    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get list of enabled plugins."""
        return [p for p in self.plugins.values() if p.enabled]

    def initialize_enabled_plugins(self):
        """Initialize all enabled plugins."""
        for plugin in self.plugins.values():
            setting_name = f"USE_{plugin.name.upper()}"
            if getattr(self.settings, setting_name, False):
                self.enable_plugin(plugin.name)

    def shutdown_all_plugins(self):
        """Shutdown all plugins."""
        for plugin in self.plugins.values():
            plugin.disable()

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report for all plugins."""
        return {
            'total_plugins': len(self.plugins),
            'available_plugins': len(self.get_available_plugins()),
            'enabled_plugins': len(self.get_enabled_plugins()),
            'plugins': {name: plugin.get_status() for name, plugin in self.plugins.items()}
        }


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager(settings) -> PluginManager:
    """Get or create the global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(settings)
    return _plugin_manager


def register_plugin(plugin: BasePlugin, settings):
    """Register a plugin with the global manager."""
    manager = get_plugin_manager(settings)
    manager.register(plugin)