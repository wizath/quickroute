"""
QuickRoute - async web framework built with FastAPI.

A modern, async web framework with familiar ORM patterns and FastAPI's performance.
"""

__version__ = "0.1.0"
__author__ = "wizath"
__email__ = "wizath@quickroute.dev"

# Core imports - provide clean interface
from .application import QuickRoute
from .settings import BaseSettings
from .models import QuickRouteModel
from .router import Router
from .database import get_async_session
from .middleware import load_middleware
from .managers import AsyncModelManager, UserManager

# Authentication imports - commonly used functions
from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    get_password_hash,
)

# Model imports for convenience
from .models import User

# Admin imports (optional)
try:
    from .admin import ADMIN_AVAILABLE, setup_admin, UserAdmin, BlacklistedTokenAdmin
except ImportError:
    ADMIN_AVAILABLE = False
    setup_admin = None
    UserAdmin = None
    BlacklistedTokenAdmin = None

# Feature imports (with graceful fallbacks)
try:
    from .websocket.decorators import websocket, websocket_room

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

try:
    from .jobs import periodic

    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False

try:
    from .plugins import BasePlugin, PluginManager

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False

__all__ = [
    # Core - interface
    "QuickRoute",
    "BaseSettings",
    "QuickRouteModel",
    "Router",
    "AsyncModelManager",
    "UserManager",
    "User",  # Common model
    "get_async_session",
    "load_middleware",
    # Authentication
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_password_hash",
    "verify_password",
    # Admin (optional)
    "ADMIN_AVAILABLE",
    "setup_admin",
    "UserAdmin",
    "BlacklistedTokenAdmin",
    # Feature availability flags
    "WEBSOCKET_AVAILABLE",
    "JOBS_AVAILABLE",
    "PLUGINS_AVAILABLE",
]

if WEBSOCKET_AVAILABLE:
    __all__.extend(["websocket", "websocket_room"])

if JOBS_AVAILABLE:
    __all__.append("periodic")

if PLUGINS_AVAILABLE:
    __all__.extend(["BasePlugin", "PluginManager"])

# Test framework imports
try:
    from .test import (
        QuickRouteTestCase,
        QuickRouteTestClient,
        test_db_engine,
        test_db_session,
        test_client,
        test_user,
        test_superuser,
        access_token,
        superuser_token,
    )

    __all__.extend(
        [
            "QuickRouteTestCase",
            "QuickRouteTestClient",
            "test_db_engine",
            "test_db_session",
            "test_client",
            "test_user",
            "test_superuser",
            "access_token",
            "superuser_token",
        ]
    )
except ImportError:
    pass
