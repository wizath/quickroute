"""
WebSocket connection and room management for QuickRoute.
"""

import asyncio
import json
from typing import Dict, List, Set, Optional, Any, Callable
from datetime import datetime
from fastapi import WebSocket
from .exceptions import WebSocketMessageError
from quickroute.logging import logger


class WebSocketConnection:
    """
    Represents a single WebSocket connection with metadata.
    """

    def __init__(self, websocket: WebSocket, connection_id: str = None):
        self.websocket = websocket
        self.connection_id = connection_id or f"conn_{id(websocket)}"
        self.user = None
        self.authenticated = False
        self.rooms: Set[str] = set()
        self.metadata: Dict[str, Any] = {}
        self.connected_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self._closed = False

    async def accept(self, subprotocol: str = None):
        """Accept the WebSocket connection."""
        try:
            await self.websocket.accept(subprotocol=subprotocol)
            self._closed = False
            logger.info(f"WebSocket connection accepted: {self.connection_id}")
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection {self.connection_id}: {e}")
            raise

    async def send_json(self, data: dict):
        """Send JSON data to the connection."""
        if self._closed:
            return

        try:
            await self.websocket.send_json(data)
            self.last_activity = datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to send JSON to {self.connection_id}: {e}")
            await self.close()

    async def send_text(self, text: str):
        """Send text data to the connection."""
        if self._closed:
            return

        try:
            await self.websocket.send_text(text)
            self.last_activity = datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to send text to {self.connection_id}: {e}")
            await self.close()

    async def receive_json(self) -> dict:
        """Receive JSON data from the connection."""
        try:
            data = await self.websocket.receive_json()
            self.last_activity = datetime.utcnow()
            return data
        except Exception as e:
            logger.error(f"Failed to receive JSON from {self.connection_id}: {e}")
            raise WebSocketMessageError(f"Invalid JSON message: {e}")

    async def receive_text(self) -> str:
        """Receive text data from the connection."""
        try:
            text = await self.websocket.receive_text()
            self.last_activity = datetime.utcnow()
            return text
        except Exception as e:
            logger.error(f"Failed to receive text from {self.connection_id}: {e}")
            raise

    async def close(self, code: int = 1000, reason: str = "Normal closure"):
        """Close the WebSocket connection."""
        if not self._closed:
            try:
                await self.websocket.close(code=code, reason=reason)
                self._closed = True
                logger.info(f"WebSocket connection closed: {self.connection_id}")
            except Exception as e:
                logger.error(f"Error closing WebSocket {self.connection_id}: {e}")

    @property
    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed

    @property
    def uptime_seconds(self) -> float:
        """Get connection uptime in seconds."""
        return (datetime.utcnow() - self.connected_at).total_seconds()

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the connection."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the connection."""
        return self.metadata.get(key, default)


class WebSocketRoom:
    """
    Represents a WebSocket room for broadcasting to multiple connections.
    """

    def __init__(self, name: str):
        self.name = name
        self.connections: Set[WebSocketConnection] = set()
        self.created_at = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}

    async def add_connection(self, connection: WebSocketConnection):
        """Add a connection to the room."""
        self.connections.add(connection)
        connection.rooms.add(self.name)
        logger.debug(f"Connection {connection.connection_id} joined room {self.name}")

    async def remove_connection(self, connection: WebSocketConnection):
        """Remove a connection from the room."""
        self.connections.discard(connection)
        connection.rooms.discard(self.name)
        logger.debug(f"Connection {connection.connection_id} left room {self.name}")

    async def broadcast_json(self, data: dict, exclude_connection: WebSocketConnection = None):
        """Broadcast JSON data to all connections in the room."""
        if not self.connections:
            return

        message = json.dumps(data)
        await self._broadcast(message, exclude_connection)

    async def broadcast_text(self, text: str, exclude_connection: WebSocketConnection = None):
        """Broadcast text data to all connections in the room."""
        if not self.connections:
            return
        await self._broadcast(text, exclude_connection)

    async def _broadcast(self, message: str, exclude_connection: WebSocketConnection = None):
        """Internal broadcast method."""
        disconnected = []

        for connection in self.connections:
            if connection == exclude_connection:
                continue

            try:
                if not connection.is_closed:
                    await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send to {connection.connection_id}: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            await self.remove_connection(connection)

    @property
    def connection_count(self) -> int:
        """Get number of active connections in the room."""
        return len([c for c in self.connections if not c.is_closed])

    @property
    def is_empty(self) -> bool:
        """Check if room has no active connections."""
        return self.connection_count == 0

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the room."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from the room."""
        return self.metadata.get(key, default)


class WebSocketManager:
    """
    Central manager for all WebSocket connections and rooms.
    """

    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.rooms: Dict[str, WebSocketRoom] = {}
        self._connection_handlers: Dict[str, Callable] = {}
        self._room_handlers: Dict[str, Callable] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 300  # 5 minutes

    async def create_connection(
        self, websocket: WebSocket, connection_id: str = None
    ) -> WebSocketConnection:
        """Create a new WebSocket connection."""
        connection = WebSocketConnection(websocket, connection_id)
        self.connections[connection.connection_id] = connection
        logger.info(f"Created WebSocket connection: {connection.connection_id}")
        return connection

    async def remove_connection(self, connection: WebSocketConnection):
        """Remove a WebSocket connection from all rooms."""
        if connection.connection_id in self.connections:
            del self.connections[connection.connection_id]

        for room_name in list(connection.rooms):
            room = self.rooms.get(room_name)
            if room:
                await room.remove_connection(connection)

        # Clean up empty rooms
        await self._cleanup_empty_rooms()
        logger.info(f"Removed WebSocket connection: {connection.connection_id}")

    async def join_room(self, connection: WebSocketConnection, room_name: str) -> WebSocketRoom:
        """Add a connection to a room."""
        if room_name not in self.rooms:
            self.rooms[room_name] = WebSocketRoom(room_name)

        room = self.rooms[room_name]
        await room.add_connection(connection)
        return room

    async def leave_room(self, connection: WebSocketConnection, room_name: str):
        """Remove a connection from a room."""
        room = self.rooms.get(room_name)
        if room:
            await room.remove_connection(connection)

    async def get_room(self, room_name: str) -> Optional[WebSocketRoom]:
        """Get a room by name."""
        return self.rooms.get(room_name)

    async def list_rooms(self) -> List[WebSocketRoom]:
        """List all active rooms."""
        return list(self.rooms.values())

    async def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get a connection by ID."""
        return self.connections.get(connection_id)

    async def list_connections(self) -> List[WebSocketConnection]:
        """List all active connections."""
        return list(self.connections.values())

    async def get_connections_in_room(self, room_name: str) -> List[WebSocketConnection]:
        """Get all connections in a specific room."""
        room = self.rooms.get(room_name)
        return list(room.connections) if room else []

    async def broadcast_to_room(
        self, room_name: str, data: Any, exclude_connection: WebSocketConnection = None
    ):
        """Broadcast data to all connections in a room."""
        room = self.rooms.get(room_name)
        if room:
            if isinstance(data, dict):
                await room.broadcast_json(data, exclude_connection)
            else:
                await room.broadcast_text(str(data), exclude_connection)

    async def broadcast_to_all(self, data: Any, exclude_connection: WebSocketConnection = None):
        """Broadcast data to all active connections."""
        message = json.dumps(data) if isinstance(data, dict) else str(data)
        disconnected = []

        for connection in self.connections.values():
            if connection == exclude_connection or connection.is_closed:
                continue

            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection.connection_id}: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            await self.remove_connection(connection)

    async def get_user_connections(self, user_id: Any) -> List[WebSocketConnection]:
        """Get all connections for a specific user."""
        return [
            conn
            for conn in self.connections.values()
            if conn.user and getattr(conn.user, "id", None) == user_id
        ]

    async def send_to_user(self, user_id: Any, data: Any):
        """Send data to all connections for a specific user."""
        connections = await self.get_user_connections(user_id)
        message = json.dumps(data) if isinstance(data, dict) else str(data)

        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(
                    f"Failed to send to user {user_id} connection {connection.connection_id}: {e}"
                )

    def register_connection_handler(self, path: str, handler: Callable):
        """Register a WebSocket connection handler for a path."""
        self._connection_handlers[path] = handler

    def register_room_handler(self, room_name: str, handler: Callable):
        """Register a WebSocket room event handler."""
        self._room_handlers[room_name] = handler

    async def _cleanup_empty_rooms(self):
        """Remove empty rooms."""
        empty_rooms = [name for name, room in self.rooms.items() if room.is_empty]
        for room_name in empty_rooms:
            del self.rooms[room_name]
            logger.debug(f"Cleaned up empty room: {room_name}")

    async def start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_stale_connections()
                await self._cleanup_empty_rooms()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket cleanup error: {e}")

    async def _cleanup_stale_connections(self):
        """Remove stale connections."""
        stale = []
        current_time = datetime.utcnow()

        for connection in self.connections.values():
            # Consider connections stale if no activity for 1 hour
            if (current_time - connection.last_activity).total_seconds() > 3600:
                stale.append(connection)

        for connection in stale:
            await connection.close(1001, "Connection stale")
            await self.remove_connection(connection)

    def get_stats(self) -> dict:
        """Get WebSocket system statistics."""
        return {
            "total_connections": len(self.connections),
            "active_connections": len([c for c in self.connections.values() if not c.is_closed]),
            "total_rooms": len(self.rooms),
            "active_rooms": len([r for r in self.rooms.values() if not r.is_empty]),
            "registered_handlers": len(self._connection_handlers),
            "room_handlers": len(self._room_handlers),
        }


# Global WebSocket manager instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
