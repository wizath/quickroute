"""
WebSocket middleware for QuickRoute.

Provides middleware support for WebSocket connections.
"""

from typing import Callable, Dict, Any
from fastapi import WebSocket
from .connection import WebSocketConnection
from .auth import get_websocket_client_manager
from quickroute.logging import logger


class WebSocketMiddleware:
    """
    Base WebSocket middleware class.
    """

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """
        Process WebSocket connection before handler.

        Args:
            websocket: FastAPI WebSocket instance
            connection: QuickRoute WebSocket connection
            call_next: Next middleware/handler in chain
        """
        pass

    async def process_message(
        self, connection: WebSocketConnection, message: Any, call_next: Callable
    ):
        """
        Process WebSocket message before handler.

        Args:
            connection: WebSocket connection
            message: Received message
            call_next: Next message handler in chain
        """
        pass


class WebSocketLoggingMiddleware(WebSocketMiddleware):
    """WebSocket logging middleware."""

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """Log WebSocket connection attempt."""
        client_host = websocket.client.host if websocket.client else "unknown"
        user_agent = websocket.headers.get("user-agent", "unknown")

        connection.add_metadata("ip_address", client_host)
        connection.add_metadata("user_agent", user_agent)

        logger.info(
            f"WebSocket connection attempt: {connection.connection_id} from {client_host} ({user_agent})"
        )

        result = await call_next(websocket, connection)

        logger.info(f"WebSocket connection closed: {connection.connection_id}")
        return result

    async def process_message(
        self, connection: WebSocketConnection, message: Any, call_next: Callable
    ):
        """Log WebSocket message."""
        logger.debug(f"WebSocket message from {connection.connection_id}: {str(message)[:100]}")
        return await call_next(connection, message)


class WebSocketSessionMiddleware(WebSocketMiddleware):
    """WebSocket session management middleware."""

    def __init__(self):
        self.client_manager = get_websocket_client_manager()

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """Register/unregister WebSocket client."""
        self.client_manager.register_client(connection)

        try:
            result = await call_next(websocket, connection)
        finally:
            # Unregister client on disconnect
            self.client_manager.unregister_client(connection)

        return result


class WebSocketAuthMiddleware(WebSocketMiddleware):
    """WebSocket authentication middleware."""

    def __init__(self, require_auth: bool = False):
        self.require_auth = require_auth

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """Check WebSocket authentication."""
        if self.require_auth and not connection.authenticated:
            logger.warning(f"Unauthorized WebSocket connection attempt: {connection.connection_id}")
            await connection.close(4003, "Authentication required")
            return

        if connection.authenticated:
            connection.add_metadata("auth_checked_at", connection.last_activity.isoformat())

        return await call_next(websocket, connection)


class WebSocketRateLimitMiddleware(WebSocketMiddleware):
    """WebSocket rate limiting middleware."""

    def __init__(self, max_connections: int = 100, max_messages_per_minute: int = 60):
        self.max_connections = max_connections
        self.max_messages_per_minute = max_messages_per_minute
        self.connection_counts: Dict[str, int] = {}

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """Check connection limits."""
        client_host = websocket.client.host if websocket.client else "unknown"
        current_connections = self.connection_counts.get(client_host, 0)

        if current_connections >= self.max_connections:
            logger.warning(f"Connection limit exceeded for {client_host}: {current_connections}")
            await connection.close(4002, "Too many connections")
            return

        # Increment connection count
        self.connection_counts[client_host] = current_connections + 1
        connection.add_metadata("rate_limit_host", client_host)

        try:
            result = await call_next(websocket, connection)
        finally:
            # Decrement connection count
            self.connection_counts[client_host] = max(
                0, self.connection_counts.get(client_host, 0) - 1
            )

        return result

    async def process_message(
        self, connection: WebSocketConnection, message: Any, call_next: Callable
    ):
        """Check message rate limits."""
        if not hasattr(connection, "_message_times"):
            connection._message_times = []

        import time

        current_time = time.time()

        # Clean old messages (older than 1 minute)
        connection._message_times = [t for t in connection._message_times if current_time - t < 60]

        if len(connection._message_times) >= self.max_messages_per_minute:
            logger.warning(f"Message rate limit exceeded for {connection.connection_id}")
            await connection.send_json(
                {
                    "type": "rate_limit",
                    "message": f"Rate limit exceeded: {self.max_messages_per_minute} messages per minute",
                }
            )
            return

        connection._message_times.append(current_time)

        return await call_next(connection, message)


class WebSocketCORSMiddleware(WebSocketMiddleware):
    """WebSocket CORS middleware."""

    def __init__(self, allowed_origins: list = None):
        self.allowed_origins = allowed_origins or ["*"]

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, call_next: Callable
    ):
        """Check CORS headers."""
        origin = websocket.headers.get("origin")

        if origin and "*" not in self.allowed_origins and origin not in self.allowed_origins:
            logger.warning(f"CORS blocked WebSocket connection from {origin}")
            await connection.close(4003, "CORS policy violation")
            return

        connection.add_metadata("origin", origin)
        return await call_next(websocket, connection)


class WebSocketMiddlewareChain:
    """
    Chain of WebSocket middleware processors.
    """

    def __init__(self):
        self.middlewares: list[WebSocketMiddleware] = []

    def add_middleware(self, middleware: WebSocketMiddleware):
        """Add middleware to the chain."""
        self.middlewares.append(middleware)

    def remove_middleware(self, middleware_class: type):
        """Remove middleware by class."""
        self.middlewares = [m for m in self.middlewares if not isinstance(m, middleware_class)]

    async def process_websocket(
        self, websocket: WebSocket, connection: WebSocketConnection, handler: Callable
    ):
        """Process WebSocket through middleware chain."""
        if not self.middlewares:
            return await handler(websocket, connection)

        # Build middleware chain
        async def create_next_middleware(index: int):
            if index >= len(self.middlewares):
                return await handler(websocket, connection)

            middleware = self.middlewares[index]

            async def next_handler(ws, conn):
                return await create_next_middleware(index + 1)

            return await middleware.process_websocket(ws, conn, next_handler)

        return await create_next_middleware(0)

    async def process_message(
        self, connection: WebSocketConnection, message: Any, handler: Callable
    ):
        """Process message through middleware chain."""
        if not self.middlewares:
            return await handler(connection, message)

        # Build middleware chain
        async def create_next_middleware(index: int):
            if index >= len(self.middlewares):
                return await handler(connection, message)

            middleware = self.middlewares[index]

            async def next_handler(conn, msg):
                return await create_next_middleware(index + 1)

            return await middleware.process_message(conn, msg, next_handler)

        return await create_next_middleware(0)


# Global middleware chain
_websocket_middleware_chain = WebSocketMiddlewareChain()


def get_websocket_middleware_chain() -> WebSocketMiddlewareChain:
    """Get the global WebSocket middleware chain."""
    return _websocket_middleware_chain


def add_websocket_middleware(middleware: WebSocketMiddleware):
    """Add middleware to the global chain."""
    _websocket_middleware_chain.add_middleware(middleware)


def remove_websocket_middleware(middleware_class: type):
    """Remove middleware from the global chain."""
    _websocket_middleware_chain.remove_middleware(middleware_class)


def initialize_default_websocket_middleware():
    """Initialize default WebSocket middleware."""
    from ..settings import settings

    add_websocket_middleware(WebSocketLoggingMiddleware())
    add_websocket_middleware(WebSocketSessionMiddleware())
    add_websocket_middleware(
        WebSocketAuthMiddleware(require_auth=getattr(settings, "WEBSOCKET_REQUIRE_AUTH", False))
    )

    if hasattr(settings, "WEBSOCKET_RATE_LIMIT") and settings.WEBSOCKET_RATE_LIMIT:
        max_connections = getattr(settings, "WEBSOCKET_MAX_CONNECTIONS", 100)
        max_messages = getattr(settings, "WEBSOCKET_MAX_MESSAGES_PER_MINUTE", 60)
        add_websocket_middleware(WebSocketRateLimitMiddleware(max_connections, max_messages))

    if hasattr(settings, "WEBSOCKET_ALLOWED_ORIGINS") and settings.WEBSOCKET_ALLOWED_ORIGINS:
        add_websocket_middleware(WebSocketCORSMiddleware(settings.WEBSOCKET_ALLOWED_ORIGINS))

    logger.info(f"Initialized {len(_websocket_middleware_chain.middlewares)} WebSocket middleware")
