"""
QuickRoute WebSocket system.

Built-in WebSocket support with patterns.
"""

from .decorators import websocket, websocket_room, websocket_auth
from .connection import WebSocketManager, get_websocket_manager, WebSocketConnection, WebSocketRoom
from .exceptions import WebSocketException, WebSocketDisconnect

__all__ = [
    'websocket',
    'websocket_room',
    'websocket_auth',
    'WebSocketManager',
    'get_websocket_manager',
    'WebSocketConnection',
    'WebSocketRoom',
    'WebSocketException',
    'WebSocketDisconnect',
]