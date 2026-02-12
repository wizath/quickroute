"""
QuickRoute application wrapper.

Provides a interface for QuickRoute applications.
"""

import os
from typing import Optional
from fastapi import FastAPI
from rich.console import Console

console = Console()


class QuickRoute:
    """
    application wrapper for QuickRoute.

    Provides a familiar interface for creating and configuring QuickRoute applications.
    """

    def __init__(
        self,
        title: str = "QuickRoute API",
        description: str = "async web framework",
        version: str = "1.0.0",
        settings_module: Optional[str] = None,
        root_path: str = "",
    ):
        """
        Initialize QuickRoute application.

        Args:
            title: Application title
            description: Application description
            version: Application version
            settings_module: Settings module path (e.g., "myproject.settings")
        """
        self.title = title
        self.description = description
        self.version = version
        self.settings_module = settings_module

        if settings_module:
            os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

        try:
            from . import settings

            self.settings = settings
        except ImportError as e:
            console.print(f"[red]Error importing settings: {e}")
            raise

        self.app = FastAPI(title=title, description=description, version=version, root_path=root_path)

        self._initialize_components()

    def _initialize_components(self):
        """Initialize QuickRoute components."""
        try:
            from . import load_middleware

            load_middleware(self.app)
        except ImportError as e:
            console.print(f"[yellow]Warning: Could not load middleware: {e}")

        try:
            from . import ADMIN_AVAILABLE, setup_admin

            if ADMIN_AVAILABLE:
                from .database import engine

                setup_admin(self.app, engine)
        except ImportError:
            pass  # Admin is optional

        try:
            from . import WEBSOCKET_AVAILABLE

            if WEBSOCKET_AVAILABLE:
                from .websocket import get_websocket_manager

                websocket_manager = get_websocket_manager()
        except ImportError:
            pass  # WebSocket is optional

        try:
            from . import PLUGINS_AVAILABLE

            if PLUGINS_AVAILABLE:
                from .plugins import initialize_plugins

                initialize_plugins(self.settings)
        except ImportError:
            pass  # Plugins are optional

        try:
            from . import JOBS_AVAILABLE

            if JOBS_AVAILABLE:
                # Jobs are auto-registered when imported
                pass
        except ImportError:
            pass  # Jobs are optional

    def get_app(self) -> FastAPI:
        """Get the underlying FastAPI application."""
        return self.app

    def include_router(self, router, prefix: str = "", tags: list = None):
        """Include a router in the application."""
        self.app.include_router(router, prefix=prefix, tags=tags)

    def mount(self, path: str, app, name: str = None):
        """Mount a sub-application."""
        self.app.mount(path, app, name=name)

    def add_middleware(self, middleware, **kwargs):
        """Add middleware to the application."""
        self.app.middleware(middleware)(**kwargs)

    def add_exception_handler(self, exc_class_or_status_code, handler):
        """Add exception handler."""
        self.app.add_exception_handler(exc_class_or_status_code, handler)

    def get_settings(self):
        """Get application settings."""
        return self.settings

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        """Run the development server."""
        import uvicorn

        uvicorn.run(self.app, host=host, port=port, **kwargs)

    def __repr__(self):
        return f"QuickRoute(title='{self.title}', version='{self.version}')"

    def __str__(self):
        return f"QuickRoute {self.version}: {self.title}"

    def __getattr__(self, name):
        """Delegate attribute access to the underlying FastAPI app."""
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        """Make QuickRoute callable as an ASGI app."""
        await self.app(scope, receive, send)


def create_app(
    title: str = "QuickRoute API",
    description: str = "async web framework",
    version: str = "1.0.0",
    settings_module: Optional[str] = None,
    **kwargs,
) -> QuickRoute:
    """
    Convenience function to create a QuickRoute application.

    Args:
        title: Application title
        description: Application description
        version: Application version
        settings_module: Settings module path
        **kwargs: Additional arguments for QuickRoute

    Returns:
        QuickRoute application instance
    """
    return QuickRoute(
        title=title,
        description=description,
        version=version,
        settings_module=settings_module,
        **kwargs,
    )


# shortcuts
def get_app() -> FastAPI:
    """Get the current QuickRoute application (Django-like)."""
    # This would be used in a way similar to Django's get_app()
    # Implementation depends on how we want to handle app registry
    raise NotImplementedError("QuickRoute does not support app registry yet.")


def get_settings():
    """Get the current settings (Django-like)."""
    from . import settings

    return settings


def setup_django(settings_module: str = None):
    """
    Configure settings.

    Args:
        settings_module: Settings module to use
    """
    if settings_module:
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module


# Convenience exports
__all__ = [
    "QuickRoute",
    "create_app",
    "get_app",
    "get_settings",
    "setup_django",
]
