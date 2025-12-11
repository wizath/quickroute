"""
Base plugin system for QuickRoute.
"""

from typing import Dict, List, Optional
import importlib
import asyncio
from quickroute.logging import logger


class BasePlugin:
    """
    Base class for all QuickRoute plugins.

    Plugins listed in INSTALLED_PLUGINS are automatically loaded and initialized.
    """

    name: str = None  # Plugin name (required)
    version: str = "1.0.0"  # Plugin version

    def __init__(self, settings):
        self.settings = settings
        self.initialized = False

    def is_available(self) -> bool:
        """
        Check if plugin dependencies are available.

        Returns True if plugin can be initialized, False otherwise.
        """
        return True

    def initialize(self):
        """
        Initialize the plugin. Can be sync or async.

        Returns True if initialization successful, False otherwise.
        """
        return True

    def shutdown(self):
        """Cleanup and shutdown the plugin. Can be sync or async."""
        pass

    def __str__(self):
        return f"{self.name} v{self.version} ({'initialized' if self.initialized else 'not initialized'})"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


class PluginManager:
    """
    Manager for all QuickRoute plugins.

    Loads plugins from INSTALLED_PLUGINS setting.
    Convention: plugin modules must export 'Plugin' class.
    """

    def __init__(self, settings):
        self.settings = settings
        self.plugins: Dict[str, BasePlugin] = {}
        self._load_installed_plugins()

    def _load_installed_plugins(self):
        """Load plugins from INSTALLED_PLUGINS setting."""
        installed = getattr(self.settings, "INSTALLED_PLUGINS", [])

        if not installed:
            logger.info("No plugins configured in INSTALLED_PLUGINS")
            return

        logger.info(f"Loading {len(installed)} plugins from INSTALLED_PLUGINS")

        for plugin_path in installed:
            try:
                # Import module
                module = importlib.import_module(plugin_path)

                # Get Plugin class (convention)
                if not hasattr(module, "Plugin"):
                    logger.error(f"Module {plugin_path} does not export 'Plugin' class")
                    continue

                plugin_class = module.Plugin

                # Instantiate
                plugin = plugin_class(self.settings)
                self.register(plugin)

                # Check availability
                if not plugin.is_available():
                    logger.error(f"Plugin {plugin.name} dependencies not available")
                    continue

                # Initialize (handle both sync and async)
                result = plugin.initialize()
                if asyncio.iscoroutinefunction(plugin.initialize):
                    # Async initialize - run in event loop
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(result)

                if result:
                    plugin.initialized = True
                    logger.info(f"Plugin {plugin.name} initialized")
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
        """Shutdown all plugins (handles both sync and async)."""
        for plugin in self.plugins.values():
            if plugin.initialized:
                try:
                    # Handle both sync and async shutdown
                    if asyncio.iscoroutinefunction(plugin.shutdown):
                        await plugin.shutdown()
                    else:
                        plugin.shutdown()

                    plugin.initialized = False
                    logger.info(f"Plugin {plugin.name} shutdown")
                except Exception as e:
                    logger.error(f"Error shutting down plugin {plugin.name}: {e}")


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
