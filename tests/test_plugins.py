"""
Tests for the simplified plugin system.
"""

import pytest
from quickroute.app.plugins.base import BasePlugin, PluginManager
from quickroute.app.settings import BaseSettings


class MockSettings(BaseSettings):
    """Mock settings for testing."""

    INSTALLED_PLUGINS = []


class SimpleTestPlugin(BasePlugin):
    """Simple test plugin for testing."""

    name = "simple_test"
    version = "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.initialize_called = False
        self.shutdown_called = False

    def is_available(self) -> bool:
        return True

    def initialize(self) -> bool:
        self.initialize_called = True
        return True

    def shutdown(self):
        self.shutdown_called = True


class UnavailablePlugin(BasePlugin):
    """Plugin with unavailable dependencies."""

    name = "unavailable"
    version = "1.0.0"

    def is_available(self) -> bool:
        return False

    def initialize(self) -> bool:
        return True

    def shutdown(self):
        pass


class FailingPlugin(BasePlugin):
    """Plugin that fails to initialize."""

    name = "failing"
    version = "1.0.0"

    def is_available(self) -> bool:
        return True

    def initialize(self) -> bool:
        return False

    def shutdown(self):
        pass


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return MockSettings()


@pytest.fixture
def plugin_manager(mock_settings):
    """Create a plugin manager with empty INSTALLED_PLUGINS."""
    return PluginManager(mock_settings)


def test_simple_plugin_initialization(mock_settings):
    """Test simple plugin initialization."""
    plugin = SimpleTestPlugin(mock_settings)

    assert plugin.name == "simple_test"
    assert plugin.version == "1.0.0"
    assert plugin.is_available() is True
    assert plugin.initialized is False


def test_plugin_lifecycle(mock_settings):
    """Test plugin initialization and shutdown lifecycle."""
    plugin = SimpleTestPlugin(mock_settings)

    # Not initialized yet
    assert plugin.initialize_called is False
    assert plugin.initialized is False

    # Initialize
    result = plugin.initialize()
    assert result is True
    assert plugin.initialize_called is True

    # Mark as initialized
    plugin.initialized = True

    # Shutdown
    plugin.shutdown()
    assert plugin.shutdown_called is True


def test_plugin_str_repr(mock_settings):
    """Test plugin string representations."""
    plugin = SimpleTestPlugin(mock_settings)

    assert "simple_test" in str(plugin)
    assert "1.0.0" in str(plugin)
    assert "not initialized" in str(plugin)

    plugin.initialized = True
    assert "initialized" in str(plugin)

    assert "SimpleTestPlugin" in repr(plugin)
    assert "simple_test" in repr(plugin)


def test_plugin_manager_empty(plugin_manager):
    """Test plugin manager with no plugins."""
    assert len(plugin_manager.plugins) == 0
    assert len(plugin_manager.list_plugins()) == 0
    assert len(plugin_manager.get_initialized_plugins()) == 0


def test_plugin_manager_register(plugin_manager, mock_settings):
    """Test registering a plugin manually."""
    plugin = SimpleTestPlugin(mock_settings)
    plugin_manager.register(plugin)

    assert len(plugin_manager.plugins) == 1
    assert plugin_manager.get("simple_test") == plugin
    assert plugin_manager.get_plugin("simple_test") == plugin


def test_plugin_manager_get_initialized(plugin_manager, mock_settings):
    """Test getting only initialized plugins."""
    plugin1 = SimpleTestPlugin(mock_settings)
    plugin1.initialized = True

    plugin2 = UnavailablePlugin(mock_settings)
    plugin2.initialized = False

    plugin_manager.register(plugin1)
    plugin_manager.register(plugin2)

    initialized = plugin_manager.get_initialized_plugins()
    assert len(initialized) == 1
    assert initialized[0] == plugin1


@pytest.mark.asyncio
async def test_plugin_manager_shutdown_async(plugin_manager, mock_settings):
    """Test asynchronous shutdown of all plugins."""
    plugin = SimpleTestPlugin(mock_settings)
    plugin.initialized = True
    plugin_manager.register(plugin)

    await plugin_manager.shutdown_all()

    assert plugin.shutdown_called is True
    assert plugin.initialized is False


def test_installed_plugins_loading():
    """Test loading plugins from INSTALLED_PLUGINS setting."""
    settings = MockSettings()
    settings.INSTALLED_PLUGINS = ["quickroute.plugins.celery"]

    manager = PluginManager(settings)

    # Celery plugin should be loaded (but may not be initialized if dependencies unavailable)
    assert "celery" in manager.plugins
    celery_plugin = manager.get("celery")
    assert celery_plugin is not None
    assert celery_plugin.name == "celery"


def test_installed_plugins_with_unavailable_dependencies():
    """Test that plugins with unavailable dependencies are registered but not initialized."""
    import sys
    import types

    # Create mock plugin module with proper Plugin export
    mock_module = types.ModuleType("mock_plugins.test_unavailable")

    class TestUnavailablePlugin(BasePlugin):
        name = "test_unavailable"
        version = "1.0.0"

        def is_available(self) -> bool:
            return False

        def initialize(self) -> bool:
            return True

        def shutdown(self):
            pass

    mock_module.Plugin = TestUnavailablePlugin
    sys.modules["mock_plugins.test_unavailable"] = mock_module

    try:
        settings = MockSettings()
        settings.INSTALLED_PLUGINS = ["mock_plugins.test_unavailable"]

        manager = PluginManager(settings)

        # Plugin should be registered
        assert "test_unavailable" in manager.plugins

        # But not initialized due to unavailable dependencies
        plugin = manager.get("test_unavailable")
        assert plugin.initialized is False

    finally:
        # Cleanup
        if "mock_plugins.test_unavailable" in sys.modules:
            del sys.modules["mock_plugins.test_unavailable"]


def test_plugin_initialization_failure():
    """Test handling of plugin that fails to initialize."""
    import sys
    import types

    # Create mock failing plugin module with proper Plugin export
    mock_module = types.ModuleType("mock_plugins.test_failing")

    class TestFailingPlugin(BasePlugin):
        name = "test_failing"
        version = "1.0.0"

        def is_available(self) -> bool:
            return True

        def initialize(self) -> bool:
            return False  # Fails to initialize

        def shutdown(self):
            pass

    mock_module.Plugin = TestFailingPlugin
    sys.modules["mock_plugins.test_failing"] = mock_module

    try:
        settings = MockSettings()
        settings.INSTALLED_PLUGINS = ["mock_plugins.test_failing"]

        manager = PluginManager(settings)

        # Plugin should be registered
        assert "test_failing" in manager.plugins

        # But not initialized due to initialization failure
        plugin = manager.get("test_failing")
        assert plugin.initialized is False

    finally:
        # Cleanup
        if "mock_plugins.test_failing" in sys.modules:
            del sys.modules["mock_plugins.test_failing"]


def test_plugin_module_without_plugin_export():
    """Test error when module doesn't export 'Plugin' class."""
    import sys
    import types

    # Create mock module without Plugin export
    mock_module = types.ModuleType("mock_plugins.no_export")
    sys.modules["mock_plugins.no_export"] = mock_module

    try:
        settings = MockSettings()
        settings.INSTALLED_PLUGINS = ["mock_plugins.no_export"]

        manager = PluginManager(settings)

        # Plugin should NOT be loaded
        assert len(manager.plugins) == 0

    finally:
        # Cleanup
        if "mock_plugins.no_export" in sys.modules:
            del sys.modules["mock_plugins.no_export"]
