"""
WebSocket authentication and authorization for QuickRoute.

Built-in authentication system with JWT token support and user management.
"""

import json
import jwt
from typing import Optional, Any, Dict, List
from datetime import datetime
from fastapi import WebSocket
from .connection import WebSocketConnection
from .exceptions import WebSocketAuthError
from ..models import User
from ..database import AsyncSessionLocal
from ..settings import settings
from quickroute.logging import logger


class WebSocketAuthenticator:
    """
    Built-in WebSocket authentication system.
    """

    def __init__(self):
        self.jwt_secret = settings.JWT_SECRET_KEY
        self.jwt_algorithm = settings.JWT_ALGORITHM
        self.token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    async def authenticate_with_token(
        self, connection: WebSocketConnection, token: str
    ) -> Optional[User]:
        """
        Authenticate WebSocket connection using JWT token.
        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            user_id = payload.get("sub")

            if not user_id:
                raise WebSocketAuthError("Invalid token: no user ID")

            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(User).where(User.id == user_id, User.is_active == True)
                )
                user = result.scalar_one_or_none()

                if not user:
                    raise WebSocketAuthError("User not found or inactive")

                connection.user = user
                connection.authenticated = True
                connection.add_metadata("authenticated_at", datetime.utcnow().isoformat())
                connection.add_metadata("auth_method", "jwt_token")

                logger.info(
                    f"WebSocket authenticated: {connection.connection_id} -> user {user.id}"
                )
                return user

        except jwt.ExpiredSignatureError:
            raise WebSocketAuthError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise WebSocketAuthError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            raise WebSocketAuthError(f"Authentication failed: {e}")

    async def authenticate_with_session(
        self, connection: WebSocketConnection, session_id: str
    ) -> Optional[User]:
        """
        Authenticate WebSocket connection using session ID.
        """
        try:
            # This would integrate with your session system
            # For now, we'll simulate session validation
            if not session_id or len(session_id) < 10:
                raise WebSocketAuthError("Invalid session ID")

            # In a real implementation, you would:
            # 1. Look up session in Redis/database
            # 2. Validate session expiration
            # 3. Get user from session
            # 4. Update session last activity

            # For demo purposes, we'll get the first active user
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(select(User).where(User.is_active == True).limit(1))
                user = result.scalar_one_or_none()

                if not user:
                    raise WebSocketAuthError("No active user found")

                connection.user = user
                connection.authenticated = True
                connection.add_metadata("authenticated_at", datetime.utcnow().isoformat())
                connection.add_metadata("auth_method", "session")
                connection.add_metadata("session_id", session_id)

                logger.info(
                    f"WebSocket authenticated via session: {connection.connection_id} -> user {user.id}"
                )
                return user

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"WebSocket session authentication error: {e}")
            raise WebSocketAuthError(f"Session authentication failed: {e}")

    async def authenticate_with_api_key(
        self, connection: WebSocketConnection, api_key: str
    ) -> Optional[User]:
        """
        Authenticate WebSocket connection using API key.
        """
        try:
            # This would integrate with your API key system
            if not api_key or len(api_key) < 20:
                raise WebSocketAuthError("Invalid API key")

            # In a real implementation, you would validate API key against database
            # For demo, we'll simulate API key validation
            if not api_key.startswith("fastdjango_"):
                raise WebSocketAuthError("Invalid API key format")

            # Extract user ID from API key (demo implementation)
            try:
                user_id = int(api_key.split("_")[1])
            except (IndexError, ValueError):
                raise WebSocketAuthError("Invalid API key format")

            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(User).where(User.id == user_id, User.is_active == True)
                )
                user = result.scalar_one_or_none()

                if not user:
                    raise WebSocketAuthError("API key user not found")

                connection.user = user
                connection.authenticated = True
                connection.add_metadata("authenticated_at", datetime.utcnow().isoformat())
                connection.add_metadata("auth_method", "api_key")
                connection.add_metadata(
                    "api_key", api_key[:10] + "..."
                )  # Store partial key for logging

                logger.info(
                    f"WebSocket authenticated via API key: {connection.connection_id} -> user {user.id}"
                )
                return user

        except WebSocketAuthError:
            raise
        except Exception as e:
            logger.error(f"WebSocket API key authentication error: {e}")
            raise WebSocketAuthError(f"API key authentication failed: {e}")


class WebSocketAuthorizer:
    """
    WebSocket authorization system for controlling access to rooms and features.
    """

    def __init__(self):
        self.room_permissions: Dict[str, List[str]] = {}
        self.user_permissions: Dict[str, List[str]] = {}

    def can_join_room(self, connection: WebSocketConnection, room_name: str) -> bool:
        """
        Check if user can join a specific room.
        """
        if not connection.authenticated:
            return False

        # Superusers can join any room
        if connection.user and getattr(connection.user, "is_superuser", False):
            return True

        allowed_users = self.room_permissions.get(room_name, [])
        if not allowed_users:
            # If no specific permissions, allow all authenticated users
            return True

        user_identifier = str(connection.user.id if connection.user else connection.connection_id)
        return user_identifier in allowed_users

    def can_send_to_room(self, connection: WebSocketConnection, room_name: str) -> bool:
        """
        Check if user can send messages to a specific room.
        """
        if not connection.authenticated:
            return False

        # Superusers can send to any room
        if connection.user and getattr(connection.user, "is_superuser", False):
            return True

        return room_name in connection.rooms

    def can_broadcast(self, connection: WebSocketConnection) -> bool:
        """
        Check if user can broadcast to all connections.
        """
        if not connection.authenticated:
            return False

        # Only superusers can broadcast to all
        return connection.user and getattr(connection.user, "is_superuser", False)

    def add_room_permission(self, room_name: str, user_ids: List[str]):
        """
        Add users to allowed list for a room.
        """
        if room_name not in self.room_permissions:
            self.room_permissions[room_name] = []
        self.room_permissions[room_name].extend(user_ids)

    def remove_room_permission(self, room_name: str, user_ids: List[str]):
        """
        Remove users from allowed list for a room.
        """
        if room_name in self.room_permissions:
            for user_id in user_ids:
                if user_id in self.room_permissions[room_name]:
                    self.room_permissions[room_name].remove(user_id)

    def get_user_permissions(self, connection: WebSocketConnection) -> Dict[str, bool]:
        """
        Get all permissions for a user.
        """
        if not connection.authenticated:
            return {}

        return {
            "can_broadcast": self.can_broadcast(connection),
            "is_superuser": connection.user and getattr(connection.user, "is_superuser", False),
            "accessible_rooms": [
                room
                for room in self.room_permissions.keys()
                if self.can_join_room(connection, room)
            ],
        }


class WebSocketClientManager:
    """
    Built-in WebSocket client management system.
    """

    def __init__(self):
        self.clients: Dict[str, WebSocketConnection] = {}
        self.user_sessions: Dict[str, List[WebSocketConnection]] = {}
        self.client_metadata: Dict[str, Dict[str, Any]] = {}

    def register_client(self, connection: WebSocketConnection):
        """
        Register a new WebSocket client.
        """
        self.clients[connection.connection_id] = connection

        # Track user sessions
        if connection.authenticated and connection.user:
            user_id = str(connection.user.id)
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(connection)

        self.client_metadata[connection.connection_id] = {
            "connected_at": connection.connected_at.isoformat(),
            "last_activity": connection.last_activity.isoformat(),
            "user_agent": connection.get_metadata("user_agent", "Unknown"),
            "ip_address": connection.get_metadata("ip_address", "Unknown"),
            "rooms_count": len(connection.rooms),
        }

        logger.info(f"Client registered: {connection.connection_id}")

    def unregister_client(self, connection: WebSocketConnection):
        """
        Unregister a WebSocket client.
        """
        if connection.connection_id in self.clients:
            del self.clients[connection.connection_id]

        if connection.authenticated and connection.user:
            user_id = str(connection.user.id)
            if user_id in self.user_sessions:
                self.user_sessions[user_id] = [
                    conn
                    for conn in self.user_sessions[user_id]
                    if conn.connection_id != connection.connection_id
                ]
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]

        if connection.connection_id in self.client_metadata:
            del self.client_metadata[connection.connection_id]

        logger.info(f"Client unregistered: {connection.connection_id}")

    def get_client(self, connection_id: str) -> Optional[WebSocketConnection]:
        """
        Get client by connection ID.
        """
        return self.clients.get(connection_id)

    def get_user_clients(self, user_id: str) -> List[WebSocketConnection]:
        """
        Get all clients for a specific user.
        """
        return self.user_sessions.get(str(user_id), [])

    def get_client_count(self) -> int:
        """
        Get total number of connected clients.
        """
        return len(self.clients)

    def get_authenticated_clients(self) -> List[WebSocketConnection]:
        """
        Get all authenticated clients.
        """
        return [client for client in self.clients.values() if client.authenticated]

    def get_clients_in_room(self, room_name: str) -> List[WebSocketConnection]:
        """
        Get all clients in a specific room.
        """
        return [client for client in self.clients.values() if room_name in client.rooms]

    def update_client_activity(self, connection: WebSocketConnection):
        """
        Update client activity timestamp.
        """
        connection.last_activity = datetime.utcnow()
        if connection.connection_id in self.client_metadata:
            self.client_metadata[connection.connection_id][
                "last_activity"
            ] = connection.last_activity.isoformat()

    def get_client_stats(self) -> Dict[str, Any]:
        """
        Get client management statistics.
        """
        return {
            "total_clients": len(self.clients),
            "authenticated_clients": len(self.get_authenticated_clients()),
            "user_sessions": len(self.user_sessions),
            "total_rooms": len(
                set(room for client in self.clients.values() for room in client.rooms)
            ),
            "average_clients_per_user": (
                sum(len(clients) for clients in self.user_sessions.values())
                / len(self.user_sessions)
                if self.user_sessions
                else 0
            ),
        }


class WebSocketBroadcaster:
    """
    Built-in WebSocket broadcasting system.
    """

    def __init__(self, client_manager: WebSocketClientManager):
        self.client_manager = client_manager

    async def broadcast_to_all(self, message: Any, exclude_connection: WebSocketConnection = None):
        """
        Broadcast message to all connected clients.
        """
        message_str = json.dumps(message) if isinstance(message, dict) else str(message)
        disconnected = []

        for client in self.client_manager.clients.values():
            if client == exclude_connection or client.is_closed:
                continue

            try:
                await client.send_text(message_str)
                self.client_manager.update_client_activity(client)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client.connection_id}: {e}")
                disconnected.append(client)

        for client in disconnected:
            self.client_manager.unregister_client(client)

        logger.info(
            f"Broadcasted message to {len(self.client_manager.clients) - len(disconnected)} clients"
        )

    async def broadcast_to_room(
        self, room_name: str, message: Any, exclude_connection: WebSocketConnection = None
    ):
        """
        Broadcast message to all clients in a specific room.
        """
        clients = self.client_manager.get_clients_in_room(room_name)
        if not clients:
            return

        message_str = json.dumps(message) if isinstance(message, dict) else str(message)
        disconnected = []

        for client in clients:
            if client == exclude_connection or client.is_closed:
                continue

            try:
                await client.send_text(message_str)
                self.client_manager.update_client_activity(client)
            except Exception as e:
                logger.error(
                    f"Failed to broadcast to room {room_name} client {client.connection_id}: {e}"
                )
                disconnected.append(client)

        for client in disconnected:
            self.client_manager.unregister_client(client)

        logger.info(
            f"Broadcasted message to room {room_name} with {len(clients) - len(disconnected)} clients"
        )

    async def broadcast_to_user(self, user_id: str, message: Any):
        """
        Broadcast message to all clients of a specific user.
        """
        clients = self.client_manager.get_user_clients(user_id)
        if not clients:
            return

        message_str = json.dumps(message) if isinstance(message, dict) else str(message)
        disconnected = []

        for client in clients:
            if client.is_closed:
                continue

            try:
                await client.send_text(message_str)
                self.client_manager.update_client_activity(client)
            except Exception as e:
                logger.error(
                    f"Failed to broadcast to user {user_id} client {client.connection_id}: {e}"
                )
                disconnected.append(client)

        for client in disconnected:
            self.client_manager.unregister_client(client)

        logger.info(
            f"Broadcasted message to user {user_id} with {len(clients) - len(disconnected)} clients"
        )

    async def send_to_client(self, connection_id: str, message: Any):
        """
        Send message to a specific client.
        """
        client = self.client_manager.get_client(connection_id)
        if not client or client.is_closed:
            return False

        try:
            message_str = json.dumps(message) if isinstance(message, dict) else str(message)
            await client.send_text(message_str)
            self.client_manager.update_client_activity(client)
            logger.info(f"Sent message to client {connection_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send to client {connection_id}: {e}")
            return False


# Global instances
_authenticator = WebSocketAuthenticator()
_authorizer = WebSocketAuthorizer()
_client_manager = WebSocketClientManager()
_broadcaster = WebSocketBroadcaster(_client_manager)


def get_websocket_authenticator() -> WebSocketAuthenticator:
    """Get the global WebSocket authenticator."""
    return _authenticator


def get_websocket_authorizer() -> WebSocketAuthorizer:
    """Get the global WebSocket authorizer."""
    return _authorizer


def get_websocket_client_manager() -> WebSocketClientManager:
    """Get the global WebSocket client manager."""
    return _client_manager


def get_websocket_broadcaster() -> WebSocketBroadcaster:
    """Get the global WebSocket broadcaster."""
    return _broadcaster


# Built-in authentication functions
async def authenticate_websocket(
    connection: WebSocketConnection, token: str = None, session_id: str = None, api_key: str = None
) -> Optional[User]:
    """
    Built-in WebSocket authentication function that tries multiple methods.
    """
    authenticator = get_websocket_authenticator()

    if token:
        return await authenticator.authenticate_with_token(connection, token)
    elif session_id:
        return await authenticator.authenticate_with_session(connection, session_id)
    elif api_key:
        return await authenticator.authenticate_with_api_key(connection, api_key)
    else:
        raise WebSocketAuthError("No authentication credentials provided")


async def extract_websocket_credentials(websocket: WebSocket) -> Dict[str, str]:
    """
    Extract authentication credentials from WebSocket request.
    """
    credentials = {}

    # Extract from query parameters
    if "token" in websocket.query_params:
        credentials["token"] = websocket.query_params["token"]
    if "session_id" in websocket.query_params:
        credentials["session_id"] = websocket.query_params["session_id"]
    if "api_key" in websocket.query_params:
        credentials["api_key"] = websocket.query_params["api_key"]

    # Extract from headers
    if "authorization" in websocket.headers:
        auth_header = websocket.headers["authorization"]
        if auth_header.startswith("Bearer "):
            credentials["token"] = auth_header[7:]
    if "x-session-id" in websocket.headers:
        credentials["session_id"] = websocket.headers["x-session-id"]
    if "x-api-key" in websocket.headers:
        credentials["api_key"] = websocket.headers["x-api-key"]

    return credentials
