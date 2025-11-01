"""
MQTT plugin for QuickRoute.

Provides MQTT broker integration for IoT messaging and pub/sub communication.
"""

from typing import Any, Dict, Optional, Callable, List
import asyncio
import json
import uuid
from functools import wraps
from .base import BasePlugin
from ..logging import logger


class MQTTAdmin:
    """Admin interface for Mosquitto Dynamic Security."""

    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
        self._response_futures = {}

    async def create_user(self, username: str, password: str, client_id: str = None) -> bool:
        """Create a new MQTT user."""
        command = {
            "commands": [{"command": "createClient", "username": username, "password": password}]
        }
        if client_id:
            command["commands"][0]["clientid"] = client_id

        return await self._send_command(command)

    async def delete_user(self, username: str) -> bool:
        """Delete an MQTT user."""
        command = {"commands": [{"command": "deleteClient", "username": username}]}
        return await self._send_command(command)

    async def set_password(self, username: str, password: str) -> bool:
        """Change user password."""
        command = {
            "commands": [
                {"command": "setClientPassword", "username": username, "password": password}
            ]
        }
        return await self._send_command(command)

    async def list_users(self) -> List[dict]:
        """List all users."""
        command = {"commands": [{"command": "listClients"}]}
        result = await self._send_command(command)
        return result.get("clients", []) if isinstance(result, dict) else []

    async def add_role(self, role_name: str) -> bool:
        """Create a new role."""
        command = {"commands": [{"command": "createRole", "rolename": role_name}]}
        return await self._send_command(command)

    async def add_acl_to_role(self, role: str, topic: str, access: str) -> bool:
        """
        Add ACL to role.

        Args:
            role: Role name
            topic: Topic pattern
            access: "publish", "subscribe", or "both"
        """
        acl_type = {
            "publish": "publishClientSend",
            "subscribe": "subscribeLiteral",
            "both": "publishClientSend",  # Will add both
        }

        commands = []

        if access in ["publish", "both"]:
            commands.append(
                {
                    "command": "addRoleACL",
                    "rolename": role,
                    "acltype": "publishClientSend",
                    "topic": topic,
                    "allow": True,
                }
            )

        if access in ["subscribe", "both"]:
            commands.append(
                {
                    "command": "addRoleACL",
                    "rolename": role,
                    "acltype": "subscribeLiteral",
                    "topic": topic,
                    "allow": True,
                }
            )

        for cmd in commands:
            result = await self._send_command({"commands": [cmd]})
            if not result:
                return False

        return True

    async def assign_role(self, username: str, role: str) -> bool:
        """Assign role to user."""
        command = {
            "commands": [{"command": "addClientRole", "username": username, "rolename": role}]
        }
        return await self._send_command(command)

    async def remove_role(self, username: str, role: str) -> bool:
        """Remove role from user."""
        command = {
            "commands": [{"command": "removeClientRole", "username": username, "rolename": role}]
        }
        return await self._send_command(command)

    async def list_roles(self) -> List[dict]:
        """List all roles."""
        command = {"commands": [{"command": "listRoles"}]}
        result = await self._send_command(command)
        return result.get("roles", []) if isinstance(result, dict) else []

    async def get_connected_clients(self) -> List[dict]:
        """Get list of connected clients."""
        # This uses $SYS topics instead of dynamic security
        # Would need to subscribe to $SYS/broker/clients/active
        return []

    async def disconnect_client(self, client_id: str) -> bool:
        """Disconnect a client."""
        command = {"commands": [{"command": "kickClient", "clientid": client_id}]}
        return await self._send_command(command)

    async def enable_client(self, username: str) -> bool:
        """Enable a client."""
        command = {"commands": [{"command": "enableClient", "username": username}]}
        return await self._send_command(command)

    async def disable_client(self, username: str) -> bool:
        """Disable a client."""
        command = {"commands": [{"command": "disableClient", "username": username}]}
        return await self._send_command(command)

    async def get_broker_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        # This would use $SYS topics
        return {}

    async def _send_command(self, command: dict) -> Any:
        """Send command to dynamic security plugin."""

        # Publish to $CONTROL/dynamic-security/v1
        topic = "$CONTROL/dynamic-security/v1"
        payload = json.dumps(command)

        # Create response future
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self._response_futures[request_id] = future

        # Publish command
        result = self.client.publish(topic, payload, qos=1)

        if result.rc != 0:
            logger.error(f"Failed to publish admin command: {result.rc}")
            return False

        # Wait for response (with timeout)
        try:
            response = await asyncio.wait_for(future, timeout=5.0)
            return response
        except asyncio.TimeoutError:
            logger.error("Admin command timeout")
            return False
        finally:
            self._response_futures.pop(request_id, None)


class MQTTPlugin(BasePlugin):
    """
    MQTT plugin for IoT messaging and pub/sub communication.

    Provides async MQTT client with automatic reconnection,
    message serialization, and optional admin interface.
    """

    name = "mqtt"
    version = "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self._admin_client = None
        self.admin = None
        self._loop = None
        self._connected = False
        self._subscriptions: Dict[str, List[Callable]] = {}

    def is_available(self) -> bool:
        """Check if paho-mqtt is installed."""
        try:
            import paho.mqtt.client as mqtt

            return True
        except ImportError:
            logger.debug("paho-mqtt not available")
            return False

    def initialize(self) -> bool:
        """Initialize MQTT client."""
        try:
            import paho.mqtt.client as mqtt

            # Get configuration
            broker_host = getattr(self.settings, "MQTT_BROKER_HOST", "localhost")
            broker_port = getattr(self.settings, "MQTT_BROKER_PORT", 1883)
            client_id = (
                getattr(self.settings, "MQTT_CLIENT_ID", None)
                or f"quickroute-{uuid.uuid4().hex[:8]}"
            )
            username = getattr(self.settings, "MQTT_USERNAME", None)
            password = getattr(self.settings, "MQTT_PASSWORD", None)
            keepalive = getattr(self.settings, "MQTT_KEEPALIVE", 60)
            clean_session = getattr(self.settings, "MQTT_CLEAN_SESSION", True)

            # Create normal client
            self.client = mqtt.Client(client_id=client_id, clean_session=clean_session)

            # Set credentials if provided
            if username and password:
                self.client.username_pw_set(username, password)

            # Configure callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # Store connection params
            self._broker_host = broker_host
            self._broker_port = broker_port
            self._keepalive = keepalive

            # Connect and start loop
            self.client.connect(self._broker_host, self._broker_port, self._keepalive)
            self.client.loop_start()

            logger.info(f"MQTT client initialized: {client_id} -> {broker_host}:{broker_port}")

            # Initialize admin client if configured
            admin_host = getattr(self.settings, "MQTT_ADMIN_HOST", None)
            if admin_host:
                self._init_admin_client()

            return True

        except Exception as e:
            logger.error(f"Failed to initialize MQTT plugin: {e}")
            return False

    def _init_admin_client(self):
        """Initialize admin MQTT client."""
        try:
            import paho.mqtt.client as mqtt

            admin_host = getattr(self.settings, "MQTT_ADMIN_HOST")
            admin_port = getattr(self.settings, "MQTT_ADMIN_PORT", 1884)
            admin_username = getattr(self.settings, "MQTT_ADMIN_USERNAME", None)
            admin_password = getattr(self.settings, "MQTT_ADMIN_PASSWORD", None)
            client_id = f"quickroute-admin-{uuid.uuid4().hex[:8]}"

            # Create admin client
            self._admin_client = mqtt.Client(client_id=client_id)

            if admin_username and admin_password:
                self._admin_client.username_pw_set(admin_username, admin_password)

            # Subscribe to response topic
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    client.subscribe("$CONTROL/dynamic-security/v1/response")
                    logger.info("MQTT admin client connected")

            def on_message(client, userdata, msg):
                # Handle admin responses
                try:
                    response = json.loads(msg.payload.decode("utf-8"))
                    # Process response
                except Exception as e:
                    logger.error(f"Error processing admin response: {e}")

            self._admin_client.on_connect = on_connect
            self._admin_client.on_message = on_message

            # Connect
            self._admin_client.connect(admin_host, admin_port, 60)
            self._admin_client.loop_start()

            # Create admin interface
            self.admin = MQTTAdmin(self._admin_client, self.settings)

            logger.info(f"MQTT admin client initialized: {admin_host}:{admin_port}")

        except Exception as e:
            logger.error(f"Failed to initialize MQTT admin client: {e}")
            self.admin = None

    def shutdown(self):
        """Disconnect from broker and cleanup."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT client disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT client: {e}")

        if self._admin_client:
            try:
                self._admin_client.loop_stop()
                self._admin_client.disconnect()
                logger.info("MQTT admin client disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT admin client: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            self._connected = True
            logger.info("MQTT client connected successfully")

            # Re-subscribe to all topics
            for topic in self._subscriptions.keys():
                qos = getattr(self.settings, "MQTT_QOS", 1)
                client.subscribe(topic, qos)
                logger.info(f"MQTT subscribed to: {topic}")
        else:
            logger.error(f"MQTT connection failed with code: {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnection: {rc}")
        else:
            logger.info("MQTT client disconnected")

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        topic = msg.topic
        payload = msg.payload

        # Find matching subscriptions
        callbacks = self._subscriptions.get(topic, [])

        # Try to decode as JSON
        try:
            message = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                message = payload.decode("utf-8")
            except UnicodeDecodeError:
                message = payload

        # Execute callbacks
        for callback in callbacks:
            try:
                if self._loop:
                    # Schedule async callback
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.run_coroutine_threadsafe(callback(topic, message), self._loop)
                    else:
                        self._loop.call_soon_threadsafe(callback, topic, message)
                else:
                    # Sync callback
                    callback(topic, message)
            except Exception as e:
                logger.error(f"Error in MQTT callback for {topic}: {e}")

    async def publish(
        self, topic: str, message: Any, qos: Optional[int] = None, retain: bool = False
    ) -> bool:
        """
        Publish message to topic.

        Args:
            topic: MQTT topic to publish to
            message: Message to publish (dict will be JSON serialized)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message

        Returns:
            True if published successfully
        """
        if not self.initialized or not self.client:
            logger.error("MQTT plugin not initialized")
            return False

        if not self._connected:
            logger.warning("MQTT client not connected, message may be queued")

        try:
            # Serialize message
            if isinstance(message, (dict, list)):
                payload = json.dumps(message)
            elif isinstance(message, str):
                payload = message
            elif isinstance(message, bytes):
                payload = message
            else:
                payload = str(message)

            # Get QoS
            if qos is None:
                qos = getattr(self.settings, "MQTT_QOS", 1)

            # Publish
            result = self.client.publish(topic, payload, qos=qos, retain=retain)

            if result.rc == 0:
                logger.debug(f"MQTT published to {topic}")
                return True
            else:
                logger.error(f"MQTT publish failed with code: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing MQTT message to {topic}: {e}")
            return False

    def subscribe(self, topic: str, qos: Optional[int] = None):
        """
        Decorator for subscribing to MQTT topics.

        Usage:
            @mqtt.subscribe("sensors/temperature")
            async def handle_temp(topic: str, message: dict):
                print(f"Temperature: {message['value']}")

        Args:
            topic: MQTT topic pattern (supports wildcards +, #)
            qos: Quality of Service level
        """

        def decorator(func: Callable) -> Callable:
            # Add to subscription registry
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []

            self._subscriptions[topic].append(func)

            # Subscribe if already connected
            if self._connected and self.client:
                qos_level = qos if qos is not None else getattr(self.settings, "MQTT_QOS", 1)
                self.client.subscribe(topic, qos_level)
                logger.info(f"MQTT subscribed to: {topic}")

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def unsubscribe(self, topic: str):
        """
        Unsubscribe from topic.

        Args:
            topic: MQTT topic to unsubscribe from
        """
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if self.client and self._connected:
            self.client.unsubscribe(topic)
            logger.info(f"MQTT unsubscribed from: {topic}")

    async def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected

    def get_subscriptions(self) -> List[str]:
        """Get list of subscribed topics."""
        return list(self._subscriptions.keys())

    async def async_initialize(self) -> bool:
        """Async initialization."""
        self._loop = asyncio.get_event_loop()
        return self.initialize()
