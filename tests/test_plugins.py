"""
Tests for the plugin system.
"""

import pytest
from quickroute.app.plugins.base import BasePlugin, PluginManager
from quickroute.app.settings import BaseSettings


class MockSettings(BaseSettings):
    """Mock settings for testing."""
    INSTALLED_PLUGINS = []


class SimpleTestPlugin(BasePlugin):
    """Simple test plugin for testing."""

    def __init__(self, settings):
        super().__init__(settings)
        self.initialize_called = False
        self.ready_called = False
        self.shutdown_called = False

    @property
    def name(self) -> str:
        return "simple_test"

    @property
    def description(self) -> str:
        return "Simple test plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def is_available(self) -> bool:
        return True

    def initialize(self) -> bool:
        self.initialize_called = True
        return True

    def ready(self):
        self.ready_called = True

    def shutdown(self):
        self.shutdown_called = True


class UnavailablePlugin(BasePlugin):
    """Plugin with unavailable dependencies."""

    @property
    def name(self) -> str:
        return "unavailable"

    @property
    def description(self) -> str:
        return "Unavailable plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def is_available(self) -> bool:
        return False

    def initialize(self) -> bool:
        return True

    def shutdown(self):
        pass


class FailingPlugin(BasePlugin):
    """Plugin that fails to initialize."""

    @property
    def name(self) -> str:
        return "failing"

    @property
    def description(self) -> str:
        return "Failing plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

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


def test_base_plugin_abstract():
    """Test that BasePlugin cannot be instantiated."""
    with pytest.raises(TypeError):
        BasePlugin(MockSettings())


def test_simple_plugin_initialization(mock_settings):
    """Test simple plugin initialization."""
    plugin = SimpleTestPlugin(mock_settings)

    assert plugin.name == "simple_test"
    assert plugin.description == "Simple test plugin"
    assert plugin.version == "1.0.0"
    assert plugin.is_available() is True
    assert plugin.initialized is False


def test_plugin_lifecycle(mock_settings):
    """Test plugin initialization, ready, and shutdown lifecycle."""
    plugin = SimpleTestPlugin(mock_settings)

    # Not initialized yet
    assert plugin.initialize_called is False
    assert plugin.ready_called is False
    assert plugin.initialized is False

    # Initialize
    result = plugin.initialize()
    assert result is True
    assert plugin.initialize_called is True

    # Mark as initialized and call ready
    plugin.initialized = True
    plugin.ready()
    assert plugin.ready_called is True

    # Shutdown
    plugin.shutdown()
    assert plugin.shutdown_called is True


def test_plugin_status(mock_settings):
    """Test plugin status reporting."""
    plugin = SimpleTestPlugin(mock_settings)

    status = plugin.get_status()
    assert status['name'] == 'simple_test'
    assert status['description'] == 'Simple test plugin'
    assert status['version'] == '1.0.0'
    assert status['initialized'] is False
    assert status['available'] is True


def test_plugin_str_repr(mock_settings):
    """Test plugin string representations."""
    plugin = SimpleTestPlugin(mock_settings)

    assert 'simple_test' in str(plugin)
    assert '1.0.0' in str(plugin)
    assert 'not initialized' in str(plugin)

    plugin.initialized = True
    assert 'initialized' in str(plugin)

    assert 'SimpleTestPlugin' in repr(plugin)
    assert 'simple_test' in repr(plugin)


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
    assert plugin_manager.get('simple_test') == plugin
    assert plugin_manager.get_plugin('simple_test') == plugin


def test_plugin_manager_status_report(plugin_manager, mock_settings):
    """Test plugin manager status report."""
    plugin1 = SimpleTestPlugin(mock_settings)
    plugin1.initialized = True

    plugin2 = UnavailablePlugin(mock_settings)

    plugin_manager.register(plugin1)
    plugin_manager.register(plugin2)

    report = plugin_manager.get_status_report()
    assert report['total_plugins'] == 2
    assert report['initialized_plugins'] == 1
    assert 'simple_test' in report['plugins']
    assert 'unavailable' in report['plugins']


def test_plugin_manager_get_initialized(plugin_manager, mock_settings):
    """Test getting only initialized plugins."""
    # Create two different plugin types so they have different names
    plugin1 = SimpleTestPlugin(mock_settings)
    plugin1.initialized = True

    plugin2 = UnavailablePlugin(mock_settings)
    plugin2.initialized = False

    plugin_manager.register(plugin1)
    plugin_manager.register(plugin2)

    initialized = plugin_manager.get_initialized_plugins()
    assert len(initialized) == 1
    assert initialized[0] == plugin1


def test_plugin_manager_shutdown_sync(plugin_manager, mock_settings):
    """Test synchronous shutdown of all plugins."""
    plugin = SimpleTestPlugin(mock_settings)
    plugin.initialized = True
    plugin_manager.register(plugin)

    plugin_manager.shutdown_all_sync()

    assert plugin.shutdown_called is True
    assert plugin.initialized is False


@pytest.mark.asyncio
async def test_plugin_manager_shutdown_async(plugin_manager, mock_settings):
    """Test asynchronous shutdown of all plugins."""
    plugin = SimpleTestPlugin(mock_settings)
    plugin.initialized = True
    plugin_manager.register(plugin)

    await plugin_manager.shutdown_all()

    assert plugin.shutdown_called is True
    assert plugin.initialized is False


@pytest.mark.asyncio
async def test_plugin_async_hooks(mock_settings):
    """Test async initialization and shutdown hooks."""
    plugin = SimpleTestPlugin(mock_settings)

    # Test async initialization (defaults to sync)
    result = await plugin.async_initialize()
    assert result is True
    assert plugin.initialize_called is True

    # Test async shutdown (defaults to sync)
    await plugin.async_shutdown()
    assert plugin.shutdown_called is True


def test_plugin_auto_discover_valid():
    """Test auto-discovery of plugin class in module."""
    plugin_class = BasePlugin.auto_discover('quickroute.app.plugins.celery_plugin')
    assert plugin_class is not None
    assert issubclass(plugin_class, BasePlugin)
    assert plugin_class.__name__ == 'CeleryPlugin'


def test_plugin_auto_discover_invalid():
    """Test auto-discovery with invalid module."""
    plugin_class = BasePlugin.auto_discover('nonexistent.module')
    assert plugin_class is None


def test_plugin_auto_discover_no_plugin():
    """Test auto-discovery in module without BasePlugin subclass."""
    plugin_class = BasePlugin.auto_discover('quickroute.app.settings')
    assert plugin_class is None


def test_installed_plugins_loading():
    """Test loading plugins from INSTALLED_PLUGINS setting."""
    settings = MockSettings()
    settings.INSTALLED_PLUGINS = ['quickroute.plugins.celery']

    manager = PluginManager(settings)

    # Celery plugin should be loaded (but may not be initialized if dependencies unavailable)
    assert 'celery' in manager.plugins
    celery_plugin = manager.get('celery')
    assert celery_plugin is not None
    assert celery_plugin.name == 'celery'


def test_installed_plugins_with_unavailable_dependencies():
    """Test that plugins with unavailable dependencies are registered but not initialized."""
    # Create a temporary plugin module for testing
    import sys
    import types

    # Create mock plugin module with proper dotted path
    mock_module = types.ModuleType('mock_plugins.test_unavailable')

    class TestUnavailablePlugin(BasePlugin):
        @property
        def name(self) -> str:
            return "test_unavailable"

        @property
        def description(self) -> str:
            return "Test unavailable"

        @property
        def version(self) -> str:
            return "1.0.0"

        def is_available(self) -> bool:
            return False

        def initialize(self) -> bool:
            return True

        def shutdown(self):
            pass

    mock_module.TestUnavailablePlugin = TestUnavailablePlugin
    sys.modules['mock_plugins.test_unavailable'] = mock_module

    try:
        settings = MockSettings()
        settings.INSTALLED_PLUGINS = ['mock_plugins.test_unavailable']

        manager = PluginManager(settings)

        # Plugin should be registered
        assert 'test_unavailable' in manager.plugins

        # But not initialized due to unavailable dependencies
        plugin = manager.get('test_unavailable')
        assert plugin.initialized is False

    finally:
        # Cleanup
        if 'mock_plugins.test_unavailable' in sys.modules:
            del sys.modules['mock_plugins.test_unavailable']


def test_plugin_manager_direct_class_path():
    """Test loading plugin with direct class path."""
    settings = MockSettings()
    settings.INSTALLED_PLUGINS = ['quickroute.app.plugins.celery_plugin.CeleryPlugin']

    manager = PluginManager(settings)

    assert 'celery' in manager.plugins
    celery_plugin = manager.get('celery')
    assert celery_plugin is not None


def test_plugin_initialization_failure():
    """Test handling of plugin that fails to initialize."""
    import sys
    import types

    # Create mock failing plugin module with proper dotted path
    mock_module = types.ModuleType('mock_plugins.test_failing')

    class TestFailingPlugin(BasePlugin):
        @property
        def name(self) -> str:
            return "test_failing"

        @property
        def description(self) -> str:
            return "Test failing"

        @property
        def version(self) -> str:
            return "1.0.0"

        def is_available(self) -> bool:
            return True

        def initialize(self) -> bool:
            return False  # Fails to initialize

        def shutdown(self):
            pass

    mock_module.TestFailingPlugin = TestFailingPlugin
    sys.modules['mock_plugins.test_failing'] = mock_module

    try:
        settings = MockSettings()
        settings.INSTALLED_PLUGINS = ['mock_plugins.test_failing']

        manager = PluginManager(settings)

        # Plugin should be registered
        assert 'test_failing' in manager.plugins

        # But not initialized due to initialization failure
        plugin = manager.get('test_failing')
        assert plugin.initialized is False

    finally:
        # Cleanup
        if 'mock_plugins.test_failing' in sys.modules:
            del sys.modules['mock_plugins.test_failing']
