"""
WebSocket decorators for QuickRoute.

decorators for WebSocket handling.
"""

import json
import asyncio
from typing import Callable, Dict, Any, Optional, Union
from functools import wraps
from fastapi import WebSocket, WebSocketDisconnect
from .connection import get_websocket_manager, WebSocketConnection
from .exceptions import WebSocketException, WebSocketDisconnect, WebSocketAuthError
from quickroute.logging import logger


def websocket(path: str, **kwargs):
    """
    Decorator for WebSocket endpoints.

    Args:
        path: WebSocket endpoint path
        **kwargs: Additional FastAPI WebSocket parameters

    Examples:
        @websocket("/ws/chat")
        async def chat_websocket(websocket, connection):
            await websocket.accept()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(websocket: WebSocket, **func_kwargs):
            manager = get_websocket_manager()

            connection = await manager.create_connection(websocket)

            try:
                # Accept connection
                await connection.accept()

                if asyncio.iscoroutinefunction(func):
                    result = await func(websocket, connection, **func_kwargs)
                else:
                    result = func(websocket, connection, **func_kwargs)

                return result

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection.connection_id}")
            except WebSocketAuthError as e:
                logger.warning(f"WebSocket auth failed: {connection.connection_id}: {e}")
                await connection.close(4003, str(e))
            except WebSocketException as e:
                logger.error(f"WebSocket error: {connection.connection_id}: {e}")
                await connection.close(4000, str(e))
            except Exception as e:
                logger.error(f"Unexpected WebSocket error: {connection.connection_id}: {e}")
                await connection.close(4000, "Internal server error")
            finally:
                # Cleanup connection
                await manager.remove_connection(connection)

        wrapper._websocket_path = path
        wrapper._websocket_kwargs = kwargs
        wrapper._is_websocket = True

        return wrapper

    return decorator


def websocket_room(room_name: str, auto_join: bool = True):
    """
    Decorator for WebSocket handlers that automatically manage room membership.

    Args:
        room_name: Name of the room
        auto_join: Whether to automatically join the room on connection

    Examples:
        @websocket_room("chat_room")
        async def chat_room_handler(websocket, connection, room):
            await room.broadcast_json({"type": "join", "user": connection.connection_id})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(websocket: WebSocket, connection: WebSocketConnection, **func_kwargs):
            manager = get_websocket_manager()

            # Join room if auto_join is enabled
            if auto_join:
                room = await manager.join_room(connection, room_name)
            else:
                room = await manager.get_room(room_name)

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(websocket, connection, room, **func_kwargs)
                else:
                    result = func(websocket, connection, room, **func_kwargs)

                return result

            except WebSocketDisconnect:
                logger.info(
                    f"Room member disconnected: {connection.connection_id} from {room_name}"
                )
                if room and not room.is_empty:
                    await room.broadcast_json(
                        {"type": "leave", "user": connection.connection_id, "room": room_name},
                        exclude_connection=connection,
                    )
            except Exception as e:
                logger.error(f"Room WebSocket error: {connection.connection_id}: {e}")
                if room:
                    await room.broadcast_json(
                        {"type": "error", "user": connection.connection_id, "error": str(e)},
                        exclude_connection=connection,
                    )
                raise

        wrapper._websocket_room = room_name
        wrapper._auto_join = auto_join
        wrapper._is_websocket = True

        return wrapper

    return decorator


def websocket_auth(auth_func: Optional[Callable] = None):
    """
    Decorator for WebSocket authentication.

    Args:
        auth_func: Function to authenticate the WebSocket connection

    Examples:
        @websocket_auth
        async def authenticate_websocket(connection, token):
            # Validate token and set user
            user = await get_user_from_token(token)
            connection.user = user
            connection.authenticated = True
            return user

        @websocket(authenticate_websocket)
        async def protected_websocket(websocket, connection):
            # Connection is authenticated here
            pass
    """

    def decorator(func: Callable = None, *, _auth_func: Callable = None) -> Callable:
        if func is None:
            # Called with parameters: @websocket_auth(auth_func)
            return lambda f: decorator(f, _auth_func=_auth_func)

        # Called without parameters: @websocket_auth
        actual_auth_func = _auth_func or auth_func

        @wraps(func)
        async def wrapper(websocket: WebSocket, connection: WebSocketConnection, **func_kwargs):
            if actual_auth_func:
                try:
                    # Extract token from query parameters or headers
                    token = None
                    if "token" in websocket.query_params:
                        token = websocket.query_params["token"]
                    elif "authorization" in websocket.headers:
                        auth_header = websocket.headers["authorization"]
                        if auth_header.startswith("Bearer "):
                            token = auth_header[7:]

                    if not token:
                        raise WebSocketAuthError("No authentication token provided")

                    if asyncio.iscoroutinefunction(actual_auth_func):
                        user = await actual_auth_func(connection, token)
                    else:
                        user = actual_auth_func(connection, token)

                    if user:
                        connection.user = user
                        connection.authenticated = True
                        logger.info(
                            f"WebSocket authenticated: {connection.connection_id} -> {user}"
                        )
                    else:
                        raise WebSocketAuthError("Authentication failed")

                except WebSocketAuthError:
                    raise
                except Exception as e:
                    logger.error(f"WebSocket authentication error: {e}")
                    raise WebSocketAuthError(f"Authentication error: {e}")

            if asyncio.iscoroutinefunction(func):
                return await func(websocket, connection, **func_kwargs)
            else:
                return func(websocket, connection, **func_kwargs)

        wrapper._websocket_auth = actual_auth_func
        wrapper._is_websocket = True

        return wrapper

    return decorator


def websocket_message_handler(message_type: str):
    """
    Decorator for handling specific message types in WebSocket handlers.

    Args:
        message_type: Type of message to handle

    Examples:
        @websocket_message_handler("chat")
        async def handle_chat_message(connection, data):
            await connection.send_json({"type": "chat_response", "data": data})
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(connection: WebSocketConnection, data: Dict[str, Any], **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(connection, data, **kwargs)
                else:
                    return func(connection, data, **kwargs)
            except Exception as e:
                logger.error(f"Message handler error for {message_type}: {e}")
                await connection.send_json(
                    {"type": "error", "message_type": message_type, "error": str(e)}
                )

        wrapper._message_type = message_type
        wrapper._is_message_handler = True

        return wrapper

    return decorator


class WebSocketRouter:
    """
    Router for organizing WebSocket handlers and message handlers.
    """

    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self.handlers: Dict[str, Callable] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.rooms: Dict[str, Callable] = {}

    def websocket(self, path: str, **kwargs):
        """Register a WebSocket handler."""

        def decorator(func: Callable) -> Callable:
            full_path = f"{self.prefix}{path}"
            handler = websocket(path, **kwargs)(func)
            self.handlers[full_path] = handler
            return handler

        return decorator

    def room(self, room_name: str, auto_join: bool = True):
        """Register a room handler."""

        def decorator(func: Callable) -> Callable:
            handler = websocket_room(room_name, auto_join)(func)
            self.rooms[room_name] = handler
            return handler

        return decorator

    def message(self, message_type: str):
        """Register a message handler."""

        def decorator(func: Callable) -> Callable:
            handler = websocket_message_handler(message_type)(func)
            self.message_handlers[message_type] = handler
            return handler

        return decorator

    def get_handler(self, path: str) -> Optional[Callable]:
        """Get WebSocket handler by path."""
        return self.handlers.get(path)

    def get_message_handler(self, message_type: str) -> Optional[Callable]:
        """Get message handler by type."""
        return self.message_handlers.get(message_type)

    def get_room_handler(self, room_name: str) -> Optional[Callable]:
        """Get room handler by name."""
        return self.rooms.get(room_name)


class WebSocketMessageProcessor:
    """
    Utility class for processing WebSocket messages with routing.
    """

    def __init__(self, router: WebSocketRouter = None):
        self.router = router or WebSocketRouter()

    async def process_message(self, connection: WebSocketConnection, message: Union[str, dict]):
        """Process a WebSocket message and route to appropriate handler."""
        try:
            # Parse message if it's a string
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    data = {"type": "text", "content": message}
            else:
                data = message

            message_type = data.get("type", "unknown")

            # Route to appropriate handler
            handler = self.router.get_message_handler(message_type)
            if handler:
                await handler(connection, data)
            else:
                # Default handler
                await self.handle_default_message(connection, data)

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await connection.send_json({"type": "error", "error": str(e)})

    async def handle_default_message(self, connection: WebSocketConnection, data: Dict[str, Any]):
        """Default message handler for unknown message types."""
        await connection.send_json(
            {
                "type": "unknown_message",
                "original_type": data.get("type", "unknown"),
                "message": "Unknown message type",
            }
        )


# Convenience functions for common patterns
def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication for WebSocket handlers."""

    @wraps(func)
    async def wrapper(websocket: WebSocket, connection: WebSocketConnection, **kwargs):
        if not connection.authenticated:
            await connection.close(4003, "Authentication required")
            return
        return await func(websocket, connection, **kwargs)

    return wrapper


def require_room(room_name: str) -> Callable:
    """Decorator to require room membership."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(websocket: WebSocket, connection: WebSocketConnection, **kwargs):
            if room_name not in connection.rooms:
                await connection.close(4003, f"Room membership required: {room_name}")
                return
            return await func(websocket, connection, **kwargs)

        return wrapper

    return decorator


def rate_limit(max_messages: int, time_window: int = 60) -> Callable:
    """Decorator to rate limit WebSocket messages."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(websocket: WebSocket, connection: WebSocketConnection, **kwargs):
            # Simple rate limiting implementation
            current_time = asyncio.get_event_loop().time()
            rate_limit_key = f"rate_limit_{connection.connection_id}"

            if not hasattr(connection, "_message_times"):
                connection._message_times = []

            # Clean old messages
            connection._message_times = [
                t for t in connection._message_times if current_time - t < time_window
            ]

            if len(connection._message_times) >= max_messages:
                await connection.send_json(
                    {
                        "type": "rate_limit",
                        "message": f"Rate limit exceeded: {max_messages} messages per {time_window} seconds",
                    }
                )
                return

            connection._message_times.append(current_time)
            return await func(websocket, connection, **kwargs)

        return wrapper

    return decorator
