"""
WebSocket examples for QuickRoute.

Demonstrates various WebSocket patterns and features.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from .decorators import websocket, websocket_room, websocket_auth, rate_limit
from .connection import get_websocket_manager
from .auth import get_websocket_broadcaster
from quickroute.logging import logger


# Example 1: Simple Echo WebSocket
@websocket("/ws/echo")
@rate_limit(max_messages=30, time_window=60)
async def echo_websocket(websocket: WebSocket, connection):
    """
    Simple echo WebSocket that returns received messages.
    """
    await connection.send_json(
        {
            "type": "welcome",
            "message": "Welcome to Echo WebSocket",
            "connection_id": connection.connection_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            data = await connection.receive_json()
            logger.info(f"Echo received: {data}")

            # Echo back the message
            echo_response = {
                "type": "echo",
                "original": data,
                "timestamp": datetime.utcnow().isoformat(),
                "connection_id": connection.connection_id,
            }

            await connection.send_json(echo_response)

    except WebSocketDisconnect:
        logger.info(f"Echo client disconnected: {connection.connection_id}")
    except Exception as e:
        logger.error(f"Echo WebSocket error: {e}")
        await connection.send_json({"type": "error", "message": str(e)})


# Example 2: Chat Room WebSocket
@websocket_room("general_chat")
@rate_limit(max_messages=60, time_window=60)
async def general_chat_websocket(websocket: WebSocket, connection, room):
    """
    General chat room WebSocket.
    """
    # Announce new user joined
    await room.broadcast_json(
        {
            "type": "user_joined",
            "user": connection.connection_id,
            "timestamp": datetime.utcnow().isoformat(),
            "room_members": len(room.connections),
        },
        exclude_connection=connection,
    )

    await connection.send_json(
        {
            "type": "welcome",
            "message": f"Welcome to General Chat! There are {len(room.connections)} users online.",
            "room": room.name,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            data = await connection.receive_json()

            if data.get("type") == "chat_message":
                chat_message = {
                    "type": "chat_message",
                    "user": connection.connection_id,
                    "message": data.get("message", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                    "room": room.name,
                }

                # Broadcast to all room members
                await room.broadcast_json(chat_message)

            elif data.get("type") == "typing":
                # Broadcast typing indicator
                await room.broadcast_json(
                    {
                        "type": "typing",
                        "user": connection.connection_id,
                        "is_typing": data.get("is_typing", False),
                    },
                    exclude_connection=connection,
                )

    except WebSocketDisconnect:
        # Announce user left
        await room.broadcast_json(
            {
                "type": "user_left",
                "user": connection.connection_id,
                "timestamp": datetime.utcnow().isoformat(),
                "room_members": len(room.connections) - 1,
            }
        )
        logger.info(f"Chat user disconnected: {connection.connection_id}")


# Example 3: Authenticated WebSocket
@websocket("/ws/protected")
@websocket_auth
async def protected_websocket(websocket: WebSocket, connection):
    """
    Protected WebSocket that requires authentication.
    """
    if not connection.authenticated:
        await connection.close(4003, "Authentication required")
        return

    await connection.send_json(
        {
            "type": "authenticated",
            "message": f"Welcome, {connection.user.email}!",
            "user_id": connection.user.id,
            "is_superuser": connection.user.is_superuser,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            data = await connection.receive_json()

            if data.get("type") == "private_message":
                target_user_id = data.get("target_user_id")
                message = data.get("message")

                if target_user_id and message:
                    broadcaster = get_websocket_broadcaster()
                    await broadcaster.broadcast_to_user(
                        target_user_id,
                        {
                            "type": "private_message",
                            "from_user": connection.user.email,
                            "from_user_id": connection.user.id,
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

            elif data.get("type") == "user_info":
                await connection.send_json(
                    {
                        "type": "user_info",
                        "user": {
                            "id": connection.user.id,
                            "email": connection.user.email,
                            "is_active": connection.user.is_active,
                            "is_superuser": connection.user.is_superuser,
                            "created_at": connection.user.created_at.isoformat(),
                        },
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"Protected client disconnected: {connection.connection_id}")


# Example 4: Real-time Notifications
@websocket_room("notifications")
@websocket_auth
async def notifications_websocket(websocket: WebSocket, connection, room):
    """
    Real-time notifications WebSocket.
    """
    # Subscribe user to their personal notifications
    personal_room = f"user_{connection.user.id}_notifications"
    manager = get_websocket_manager()
    await manager.join_room(connection, personal_room)

    await connection.send_json(
        {
            "type": "subscribed",
            "message": "Subscribed to real-time notifications",
            "rooms": [room.name, personal_room],
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            # Keep connection alive and handle ping/pong
            data = await connection.receive_json()

            if data.get("type") == "ping":
                await connection.send_json(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                )

            elif data.get("type") == "mark_read":
                # Mark notification as read
                notification_id = data.get("notification_id")
                await connection.send_json(
                    {
                        "type": "notification_read",
                        "notification_id": notification_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"Notifications client disconnected: {connection.connection_id}")


# Example 5: Multi-room WebSocket
@websocket("/ws/multiroom")
@websocket_auth
async def multiroom_websocket(websocket: WebSocket, connection):
    """
    WebSocket that can join multiple rooms.
    """
    manager = get_websocket_manager()

    await connection.send_json(
        {
            "type": "welcome",
            "message": "Multi-room WebSocket. Use 'join_room' messages to join rooms.",
            "available_rooms": ["general", "tech", "random", "support"],
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            data = await connection.receive_json()

            if data.get("type") == "join_room":
                room_name = data.get("room")
                if room_name:
                    room = await manager.join_room(connection, room_name)
                    await connection.send_json(
                        {
                            "type": "joined_room",
                            "room": room_name,
                            "members": room.connection_count,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            elif data.get("type") == "leave_room":
                room_name = data.get("room")
                if room_name:
                    await manager.leave_room(connection, room_name)
                    await connection.send_json(
                        {
                            "type": "left_room",
                            "room": room_name,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            elif data.get("type") == "room_message":
                room_name = data.get("room")
                message = data.get("message")
                if room_name and message:
                    room = await manager.get_room(room_name)
                    if room:
                        await room.broadcast_json(
                            {
                                "type": "room_message",
                                "room": room_name,
                                "user": connection.user.email,
                                "message": message,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )

            elif data.get("type") == "list_rooms":
                rooms_info = []
                for room_name in connection.rooms:
                    room = await manager.get_room(room_name)
                    if room:
                        rooms_info.append({"name": room_name, "members": room.connection_count})

                await connection.send_json(
                    {
                        "type": "rooms_list",
                        "rooms": rooms_info,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"Multi-room client disconnected: {connection.connection_id}")


# Example 6: File Progress WebSocket
@websocket_room("file_uploads")
@websocket_auth
async def file_progress_websocket(websocket: WebSocket, connection, room):
    """
    File upload progress WebSocket.
    """
    await connection.send_json(
        {
            "type": "ready",
            "message": "File progress monitoring ready",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    try:
        while True:
            data = await connection.receive_json()

            if data.get("type") == "start_upload":
                file_id = data.get("file_id")
                filename = data.get("filename")
                file_size = data.get("file_size")

                # Simulate file upload progress
                await simulate_file_upload(connection, room, file_id, filename, file_size)

    except WebSocketDisconnect:
        logger.info(f"File progress client disconnected: {connection.connection_id}")


async def simulate_file_upload(connection, room, file_id, filename, file_size):
    """Simulate file upload with progress updates."""
    chunk_size = file_size // 10  # 10 chunks
    uploaded = 0

    await room.broadcast_json(
        {
            "type": "upload_started",
            "file_id": file_id,
            "filename": filename,
            "file_size": file_size,
            "user": connection.user.email,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    for i in range(10):
        await asyncio.sleep(1)  # Simulate upload time
        uploaded += chunk_size
        progress = min(100, (uploaded / file_size) * 100)

        await room.broadcast_json(
            {
                "type": "upload_progress",
                "file_id": file_id,
                "filename": filename,
                "progress": round(progress, 1),
                "uploaded": uploaded,
                "total": file_size,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    # Upload complete
    await room.broadcast_json(
        {
            "type": "upload_complete",
            "file_id": file_id,
            "filename": filename,
            "file_url": f"/uploads/{file_id}_{filename}",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# Example 7: System Status WebSocket
@websocket_room("system_status")
async def system_status_websocket(websocket: WebSocket, connection, room):
    """
    System status monitoring WebSocket.
    """
    manager = get_websocket_manager()

    await send_system_status(room)

    try:
        while True:
            # Wait for status requests
            data = await connection.receive_json()

            if data.get("type") == "get_status":
                await send_system_status(room)

            elif data.get("type") == "get_connections":
                stats = manager.get_stats()
                await room.broadcast_json(
                    {
                        "type": "connections_status",
                        "stats": stats,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info(f"System status client disconnected: {connection.connection_id}")


async def send_system_status(room):
    """Send system status information."""
    import psutil
    from ..websocket.auth import get_websocket_client_manager

    # System stats
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    client_manager = get_websocket_client_manager()
    client_stats = client_manager.get_client_stats()

    status = {
        "type": "system_status",
        "cpu_percent": cpu_percent,
        "memory": {"total": memory.total, "available": memory.available, "percent": memory.percent},
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100,
        },
        "websocket_clients": client_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }

    await room.broadcast_json(status)


# Utility functions for examples
async def send_notification_to_user(user_id: int, notification: Dict[str, Any]):
    """
    Send notification to a specific user.
    """
    broadcaster = get_websocket_broadcaster()
    await broadcaster.broadcast_to_user(
        str(user_id),
        {"type": "notification", **notification, "timestamp": datetime.utcnow().isoformat()},
    )


async def broadcast_system_message(message: str, message_type: str = "system"):
    """
    Broadcast system message to all authenticated users.
    """
    broadcaster = get_websocket_broadcaster()
    await broadcaster.broadcast_to_all(
        {"type": message_type, "message": message, "timestamp": datetime.utcnow().isoformat()}
    )
