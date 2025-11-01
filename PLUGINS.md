# QuickRoute Plugin System

QuickRoute uses a Django-inspired plugin system that allows you to extend the framework with additional functionality like Celery task processing, InfluxDB integration, MQTT connectivity, and custom business logic.

## Quick Start

### 1. Declare Your Plugins

In your `settings.py`, add plugins to `INSTALLED_PLUGINS`:

```python
# settings.py
INSTALLED_PLUGINS = [
    'quickroute.plugins.celery',
    'myproject.plugins.custom',
]
```

That's it! If a plugin is in the list, it's loaded and initialized. If it's not, it's not loaded. Simple.

### 2. Use the Plugin

```python
from quickroute.plugins import get_plugin_manager

# Get the plugin manager
plugin_manager = get_plugin_manager(settings)

# Get a specific plugin
celery = plugin_manager.get("celery")

# Use the plugin
if celery and celery.initialized:
    result = await celery.execute(my_task, arg1, arg2)
```

## Architecture

### Django-Style Registration

Just like Django's `INSTALLED_APPS`, QuickRoute uses `INSTALLED_PLUGINS`:

```python
# Django
INSTALLED_APPS = [
    'django.contrib.admin',
    'myapp',
]

# QuickRoute
INSTALLED_PLUGINS = [
    'quickroute.plugins.celery',
    'myproject.plugins.custom',
]
```

**Auto-Discovery:**
- `'quickroute.plugins.celery'` → Auto-finds `CeleryPlugin` class in that module
- `'quickroute.plugins.celery.CeleryPlugin'` → Direct class path also works

### Plugin Lifecycle

1. **Load** - Plugin class is imported from `INSTALLED_PLUGINS`
2. **Check** - `is_available()` checks if dependencies exist
3. **Initialize** - `initialize()` sets up the plugin
4. **Ready** - `ready()` hook for post-initialization tasks
5. **Shutdown** - `shutdown()` cleans up resources on app shutdown

### Base Plugin Structure

```python
from quickroute.plugins import BasePlugin

class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def description(self) -> str:
        return "My custom plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def is_available(self) -> bool:
        """Check if dependencies are available."""
        try:
            import some_dependency
            return True
        except ImportError:
            return False

    def initialize(self) -> bool:
        """Initialize the plugin."""
        self.client = setup_client()
        return True

    def ready(self):
        """Post-initialization hook (optional)."""
        # Register signals, routes, etc.
        pass

    def shutdown(self):
        """Cleanup resources."""
        if hasattr(self, 'client'):
            self.client.close()
```

### Async Support

Plugins support async initialization and shutdown:

```python
class MyAsyncPlugin(BasePlugin):
    async def async_initialize(self) -> bool:
        """Async initialization."""
        self.pool = await create_connection_pool()
        return True

    async def async_shutdown(self):
        """Async cleanup."""
        await self.pool.close()
```

## Available Plugins

### Celery Plugin

Distributed task processing with Celery and fallback to synchronous execution.

**Add to `INSTALLED_PLUGINS`:**
```python
INSTALLED_PLUGINS = [
    'quickroute.plugins.celery',
]
```

**Configuration:**
```python
# settings.py
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
```

**Usage:**
```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
celery = plugin_manager.get("celery")

# Define task
@celery.task(name="send_email")
def send_email_task(user_id: int, message: str):
    return f"Email sent to user {user_id}"

# Execute task and await result
result = await celery.execute(send_email_task, 123, "Hello!")

# Periodic task
@celery.periodic_task("0 */6 * * *", name="cleanup")
def cleanup_task():
    # Cleanup logic
    pass
```

**Features:**
- `@task()` decorator for task creation
- `@periodic_task()` for scheduled tasks
- `await execute()` for async task execution
- Automatic fallback to sync execution when Celery unavailable
- Task status monitoring
- Redis connection checking

### InfluxDB Plugin (Planned)

Time-series database integration for metrics, logs, and IoT data.

```python
INSTALLED_PLUGINS = [
    'quickroute.plugins.influxdb',
]

# Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "your-token"
INFLUXDB_ORG = "your-org"
INFLUXDB_BUCKET = "metrics"
```

### MQTT Plugin (Planned)

MQTT broker integration for IoT messaging.

```python
INSTALLED_PLUGINS = [
    'quickroute.plugins.mqtt',
]

# Configuration
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "username"
MQTT_PASSWORD = "password"
```

## Creating Custom Plugins

### 1. Create Plugin Class

```python
# myproject/plugins/custom.py
from quickroute.plugins import BasePlugin

class CustomPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "My custom plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    def is_available(self) -> bool:
        try:
            import my_dependency
            return True
        except ImportError:
            return False

    def initialize(self) -> bool:
        self.client = setup_my_service()
        return True

    def shutdown(self):
        self.client.disconnect()

    # Custom methods
    def do_something(self, data):
        return self.client.process(data)
```

### 2. Add to INSTALLED_PLUGINS

```python
# settings.py
INSTALLED_PLUGINS = [
    'quickroute.plugins.celery',
    'myproject.plugins.custom',  # Auto-discovers CustomPlugin
]
```

### 3. Use Your Plugin

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
custom = plugin_manager.get("custom")

if custom and custom.initialized:
    result = custom.do_something({"key": "value"})
```

## Advanced Features

### ready() Hook

Use the `ready()` hook for post-initialization tasks:

```python
class MyPlugin(BasePlugin):
    def ready(self):
        """Called after initialization completes."""
        # Register signals
        self.register_signals()

        # Set up routes
        self.register_routes()

        # Connect to other plugins
        cache = self.get_plugin_manager().get("cache")
        if cache:
            self.cache = cache
```

### Plugin Status

Check plugin status at runtime:

```python
plugin_manager = get_plugin_manager(settings)

# Get status for all plugins
status = plugin_manager.get_status_report()
print(status)
# {
#     'total_plugins': 2,
#     'initialized_plugins': 1,
#     'plugins': {
#         'celery': {'initialized': True, 'available': True, ...},
#         'influxdb': {'initialized': False, 'available': False, ...}
#     }
# }

# Get specific plugin status
celery = plugin_manager.get("celery")
if celery:
    print(celery.get_status())
```

### Async Lifecycle Hooks

For async operations:

```python
plugin_manager = get_plugin_manager(settings)

# Async shutdown (called on app shutdown)
await plugin_manager.shutdown_all()

# Or sync shutdown
plugin_manager.shutdown_all_sync()
```

## Distributing Plugins

### Create Installable Plugin Package

```python
# setup.py
from setuptools import setup

setup(
    name="quickroute-myplugin",
    version="1.0.0",
    packages=["myplugin"],
    install_requires=["quickroute>=0.1.0"],
)
```

### Users Install and Use

```bash
pip install quickroute-myplugin
```

```python
# settings.py
INSTALLED_PLUGINS = [
    'myplugin',  # Just add the module path
]
```

## Best Practices

1. **Explicit Declaration**: Always list plugins in `INSTALLED_PLUGINS`
2. **Dependency Checking**: Implement `is_available()` to check dependencies
3. **Error Handling**: Handle initialization failures gracefully
4. **Resource Cleanup**: Always implement `shutdown()` to clean up resources
5. **Configuration**: Use namespaced settings (e.g., `MYPLUGIN_*`)
6. **Documentation**: Document configuration options and usage
7. **Testing**: Write tests for your plugin's lifecycle

## Comparison with Other Frameworks

### Django
```python
# Django
INSTALLED_APPS = ['django.contrib.admin', 'myapp']

# QuickRoute
INSTALLED_PLUGINS = ['quickroute.plugins.celery', 'myproject.plugins.custom']
```
Same pattern, familiar to Django developers.

### Flask
```python
# Flask (requires manual init)
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
db.init_app(app)

# QuickRoute (automatic from settings)
INSTALLED_PLUGINS = ['quickroute.plugins.sqlalchemy']
```
QuickRoute is more declarative.

### FastAPI
```python
# FastAPI (no built-in plugin system)
@app.on_event("startup")
async def startup():
    setup_services()

# QuickRoute (declarative with lifecycle)
INSTALLED_PLUGINS = ['myproject.plugins.services']
```
QuickRoute provides standardized plugin interface.

## Migration from Old System

If you're upgrading from the old `USE_*` flags:

**Old:**
```python
USE_CELERY = True
USE_CACHE = True
```

**New:**
```python
INSTALLED_PLUGINS = [
    'quickroute.plugins.celery',
    'quickroute.plugins.cache',
]
```

Much simpler! Just list what you want, everything else is automatic.