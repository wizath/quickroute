"""
Base plugin system for QuickRoute.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
import importlib
from ..logging import logger


class BasePlugin(ABC):
    """
    Base class for all QuickRoute plugins.

    Plugins listed in INSTALLED_PLUGINS are automatically loaded and initialized.
    """

    def __init__(self, settings):
        self.settings = settings
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

    async def async_initialize(self) -> bool:
        """
        Async initialization hook.

        Override this for plugins that need async initialization.
        Defaults to calling synchronous initialize().
        """
        return self.initialize()

    async def async_shutdown(self):
        """
        Async shutdown hook.

        Override this for plugins that need async cleanup.
        Defaults to calling synchronous shutdown().
        """
        self.shutdown()

    def ready(self):
        """
        Called after plugin initialization completes.

        Override this to perform post-initialization tasks like:
        - Signal registration
        - Setting up dependencies with other plugins
        - Registering routes or middleware
        """
        pass

    @classmethod
    def auto_discover(cls, module_path: str) -> Optional[Type['BasePlugin']]:
        """
        Auto-discover plugin class in a module.

        Looks for a BasePlugin subclass in the given module path.
        Returns the first BasePlugin subclass found, or None.
        """
        try:
            module = importlib.import_module(module_path)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (isinstance(attr, type) and
                    issubclass(attr, BasePlugin) and
                    attr != BasePlugin and
                    not attr.__name__.startswith('_')):
                    return attr

            logger.warning(f"No plugin class found in module: {module_path}")
            return None

        except ImportError as e:
            logger.error(f"Failed to import plugin module {module_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error discovering plugin in {module_path}: {e}")
            return None

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
            'initialized': self.initialized,
            'available': self.is_available(),
        }

    def __str__(self):
        return f"{self.name} v{self.version} ({'initialized' if self.initialized else 'not initialized'})"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PluginManager:
    """
    Manager for all QuickRoute plugins.

    Loads plugins from INSTALLED_PLUGINS setting (Django-style).
    """

    def __init__(self, settings):
        self.settings = settings
        self.plugins: Dict[str, BasePlugin] = {}
        self._load_installed_plugins()

    def _resolve_plugin_class(self, plugin_path: str) -> Optional[Type[BasePlugin]]:
        """
        Resolve plugin class from path.

        Supports two formats:
        1. 'module.path' - Auto-discovers plugin class in module
        2. 'module.path.PluginClass' - Direct class reference
        """
        if '.' not in plugin_path:
            logger.error(f"Invalid plugin path: {plugin_path}")
            return None

        parts = plugin_path.split('.')
        last_part = parts[-1]

        if last_part[0].isupper():
            try:
                module_path = '.'.join(parts[:-1])
                module = importlib.import_module(module_path)
                plugin_class = getattr(module, last_part)

                if isinstance(plugin_class, type) and issubclass(plugin_class, BasePlugin):
                    return plugin_class
                else:
                    logger.error(f"{plugin_path} is not a BasePlugin subclass")
                    return None

            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to import plugin class {plugin_path}: {e}")
                return None
        else:
            return BasePlugin.auto_discover(plugin_path)

    def _load_installed_plugins(self):
        """Load plugins from INSTALLED_PLUGINS setting."""
        installed = getattr(self.settings, 'INSTALLED_PLUGINS', [])

        if not installed:
            logger.info("No plugins configured in INSTALLED_PLUGINS")
            return

        logger.info(f"Loading {len(installed)} plugins from INSTALLED_PLUGINS")

        for plugin_path in installed:
            try:
                plugin_class = self._resolve_plugin_class(plugin_path)

                if plugin_class:
                    plugin = plugin_class(self.settings)
                    self.register(plugin)

                    if not plugin.is_available():
                        logger.error(f"Plugin {plugin.name} dependencies not available")
                        continue

                    if plugin.initialize():
                        plugin.initialized = True
                        plugin.ready()
                        logger.info(f"Plugin {plugin.name} initialized and ready")
                    else:
                        logger.error(f"Plugin {plugin.name} failed to initialize")

            except Exception as e:
                logger.error(f"Error loading plugin {plugin_path}: {e}")

    def register(self, plugin: BasePlugin):
        """Register a plugin."""
        self.plugins[plugin.name] = plugin
        logger.info(f"Registered plugin: {plugin}")

    def get(self, name: str) -> Optional[BasePlugin]:
        """Get plugin by name."""
        return self.plugins.get(name)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get plugin by name (alias for get())."""
        return self.get(name)

    def list_plugins(self) -> List[BasePlugin]:
        """List all registered plugins."""
        return list(self.plugins.values())

    def get_initialized_plugins(self) -> List[BasePlugin]:
        """Get list of initialized plugins."""
        return [p for p in self.plugins.values() if p.initialized]

    async def shutdown_all(self):
        """Shutdown all plugins asynchronously."""
        for plugin in self.plugins.values():
            if plugin.initialized:
                try:
                    await plugin.async_shutdown()
                    plugin.initialized = False
                    logger.info(f"Plugin {plugin.name} shutdown")
                except Exception as e:
                    logger.error(f"Error shutting down plugin {plugin.name}: {e}")

    def shutdown_all_sync(self):
        """Shutdown all plugins synchronously."""
        for plugin in self.plugins.values():
            if plugin.initialized:
                try:
                    plugin.shutdown()
                    plugin.initialized = False
                except Exception as e:
                    logger.error(f"Error shutting down plugin {plugin.name}: {e}")

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report for all plugins."""
        return {
            'total_plugins': len(self.plugins),
            'initialized_plugins': len(self.get_initialized_plugins()),
            'plugins': {name: plugin.get_status() for name, plugin in self.plugins.items()}
        }


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager(settings) -> PluginManager:
    """
    Get or create the global plugin manager.

    Plugins are automatically loaded from INSTALLED_PLUGINS setting.
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(settings)
    return _plugin_manager