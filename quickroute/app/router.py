"""
Simple FastAPI router with decorator-based routing and WebSocket support.

Simplified routing system focused on FastAPI decorators with built-in WebSocket support.
"""

from typing import Callable, List, Optional, Union
from fastapi import APIRouter, FastAPI
from .logging import logger


class Router:
    """
    Simple FastAPI router wrapper with WebSocket support.

    Provides a clean interface for decorator-based routing and WebSocket endpoints.
    """

    def __init__(self, prefix: str = "", tags: Optional[List[str]] = None):
        self.prefix = prefix
        self.tags = tags or []
        # FastAPI requires prefix to start with '/' if provided
        fastapi_prefix = prefix if not prefix else ""
        if fastapi_prefix and not fastapi_prefix.startswith("/"):
            fastapi_prefix = "/" + fastapi_prefix
        self.router = APIRouter(prefix=fastapi_prefix, tags=tags)
        self.websocket_handlers: List[Callable] = []

    def get(self, path: str, **kwargs):
        """GET method decorator."""
        return self.router.get(path, **kwargs)

    def post(self, path: str, **kwargs):
        """POST method decorator."""
        return self.router.post(path, **kwargs)

    def put(self, path: str, **kwargs):
        """PUT method decorator."""
        return self.router.put(path, **kwargs)

    def delete(self, path: str, **kwargs):
        """DELETE method decorator."""
        return self.router.delete(path, **kwargs)

    def patch(self, path: str, **kwargs):
        """PATCH method decorator."""
        return self.router.patch(path, **kwargs)

    def options(self, path: str, **kwargs):
        """OPTIONS method decorator."""
        return self.router.options(path, **kwargs)

    def head(self, path: str, **kwargs):
        """HEAD method decorator."""
        return self.router.head(path, **kwargs)

    def trace(self, path: str, **kwargs):
        """TRACE method decorator."""
        return self.router.trace(path, **kwargs)

    def websocket(self, path: str, **kwargs):
        """
        WebSocket endpoint decorator.

        Integrates with QuickRoute's WebSocket system.
        """
        from .websocket.decorators import websocket

        def decorator(func: Callable) -> Callable:
            handler = websocket(path, **kwargs)(func)
            self.websocket_handlers.append(handler)
            return handler

        return decorator

    def websocket_room(self, room_name: str, path: str = None, auto_join: bool = True, **kwargs):
        """
        WebSocket room endpoint decorator.

        Automatically manages room membership.
        """
        from .websocket.decorators import websocket_room

        def decorator(func: Callable) -> Callable:
            ws_path = path or f"/ws/{room_name}"
            handler = websocket_room(room_name, auto_join)(func)

            @self.websocket(ws_path, **kwargs)
            async def room_websocket(websocket, connection):
                return await handler(websocket, connection)

            return handler

        return decorator

    def include_router(self, router: Union[APIRouter, "Router"], prefix: str = ""):
        """Include another router."""
        if isinstance(router, Router):
            # Include WebSocket handlers from child router
            self.websocket_handlers.extend(router.websocket_handlers)
            self.router.include_router(router.router, prefix=prefix)
        else:
            self.router.include_router(router, prefix=prefix)

    def register_with_app(self, app: FastAPI):
        """Register this router with FastAPI app including WebSocket handlers."""
        app.include_router(self.router)

        for handler in self.websocket_handlers:
            if hasattr(handler, "_websocket_path"):
                ws_path = handler._websocket_path
                ws_kwargs = handler._websocket_kwargs or {}

                @app.websocket(ws_path, **ws_kwargs)
                async def websocket_wrapper(websocket, _handler=handler):
                    return await _handler(websocket)

        logger.info(
            f"Registered router with prefix: {self.prefix} (HTTP routes + {len(self.websocket_handlers)} WebSocket routes)"
        )

    def route(self, path: str, methods: List[str], **kwargs):
        """Generic route decorator for multiple methods."""
        return self.router.route(path, methods=methods, **kwargs)

    def get_websocket_handlers(self) -> List[Callable]:
        """Get all registered WebSocket handlers."""
        return self.websocket_handlers.copy()

    def has_websockets(self) -> bool:
        """Check if this router has WebSocket handlers."""
        return len(self.websocket_handlers) > 0


# Convenience function for creating WebSocket-only routers
def WebSocketRouter(prefix: str = "", tags: Optional[List[str]] = None) -> Router:
    """
    Create a router optimized for WebSocket endpoints.
    """
    router = Router(prefix=prefix, tags=tags or ["websocket"])
    return router
