# MQTT Plugin for QuickRoute

MQTT (Message Queuing Telemetry Transport) plugin for IoT messaging, real-time notifications, and pub/sub communication.

## Installation

```bash
pip install paho-mqtt
```

## Configuration

Add to your `settings.py`:

```python
# Add MQTT plugin
INSTALLED_PLUGINS = [
    'quickroute.plugins.mqtt',
]

# MQTT Configuration
MQTT_BROKER_HOST = "localhost"          # MQTT broker hostname
MQTT_BROKER_PORT = 1883                 # MQTT broker port (1883 for TCP, 8883 for TLS)
MQTT_USERNAME = "your-username"         # Optional
MQTT_PASSWORD = "your-password"         # Optional
MQTT_CLIENT_ID = None                   # Auto-generated if not set
MQTT_KEEPALIVE = 60                     # Keepalive interval in seconds
MQTT_QOS = 1                            # Default Quality of Service (0, 1, or 2)
MQTT_CLEAN_SESSION = True               # Clean session flag
```

## Quick Start

### 1. Publishing Messages

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
mqtt = plugin_manager.get("mqtt")

# Publish a message
await mqtt.publish("sensors/temperature", {"value": 23.5, "unit": "celsius"})

# Publish with QoS and retain
await mqtt.publish("devices/status", {"online": True}, qos=2, retain=True)

# Publish raw string
await mqtt.publish("logs/info", "Application started")

# Publish raw bytes
await mqtt.publish("data/binary", b"\x00\x01\x02")
```

### 2. Subscribing to Topics

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
mqtt = plugin_manager.get("mqtt")

# Subscribe with decorator
@mqtt.subscribe("sensors/temperature")
async def handle_temperature(topic: str, message: dict):
    print(f"Temperature: {message['value']}°{message['unit']}")

# Subscribe to multiple topics
@mqtt.subscribe("sensors/humidity")
@mqtt.subscribe("sensors/pressure")
async def handle_sensor_data(topic: str, message: dict):
    sensor_type = topic.split('/')[-1]
    print(f"{sensor_type}: {message}")

# Wildcard subscriptions
@mqtt.subscribe("devices/+/status")  # Single level wildcard
async def handle_device_status(topic: str, message: dict):
    device_id = topic.split('/')[1]
    print(f"Device {device_id} status: {message}")

@mqtt.subscribe("sensors/#")  # Multi-level wildcard
async def handle_all_sensors(topic: str, message: dict):
    print(f"Sensor data from {topic}: {message}")
```

### 3. Using in Routes

```python
from fastapi import APIRouter
from quickroute.plugins import get_plugin_manager
from quickroute import settings

router = APIRouter()

@router.post("/devices/{device_id}/control")
async def control_device(device_id: str, command: dict):
    """Send control command to IoT device via MQTT."""
    plugin_manager = get_plugin_manager(settings)
    mqtt = plugin_manager.get("mqtt")

    if mqtt and mqtt.initialized:
        topic = f"devices/{device_id}/commands"
        success = await mqtt.publish(topic, command)

        if success:
            return {"status": "command_sent", "device_id": device_id}
        else:
            return {"status": "error", "message": "Failed to publish command"}
    else:
        return {"status": "error", "message": "MQTT not available"}

@router.get("/mqtt/status")
async def mqtt_status():
    """Get MQTT plugin status."""
    plugin_manager = get_plugin_manager(settings)
    mqtt = plugin_manager.get("mqtt")

    if mqtt:
        return mqtt.get_status()
    else:
        return {"status": "not_initialized"}
```

## API Reference

### Publishing

#### `async def publish(topic: str, message: Any, qos: int = None, retain: bool = False) -> bool`

Publish a message to an MQTT topic.

**Parameters:**
- `topic` (str): MQTT topic to publish to
- `message` (Any): Message to publish (dict/list = JSON, str = string, bytes = raw)
- `qos` (int, optional): Quality of Service level (0, 1, or 2). Defaults to MQTT_QOS setting
- `retain` (bool): Whether to retain the message on the broker

**Returns:**
- `bool`: True if published successfully

**Example:**
```python
# JSON message
await mqtt.publish("sensors/temp", {"value": 25.0})

# With QoS 2 and retain
await mqtt.publish("config/settings", {"mode": "auto"}, qos=2, retain=True)
```

### Subscribing

#### `@mqtt.subscribe(topic: str, qos: int = None)`

Decorator for subscribing to MQTT topics.

**Parameters:**
- `topic` (str): MQTT topic pattern (supports wildcards `+` and `#`)
- `qos` (int, optional): Quality of Service level

**Example:**
```python
@mqtt.subscribe("sensors/temperature", qos=2)
async def handle_temp(topic: str, message: dict):
    print(f"Got temperature: {message}")
```

#### `def unsubscribe(topic: str)`

Unsubscribe from a topic.

**Parameters:**
- `topic` (str): MQTT topic to unsubscribe from

**Example:**
```python
mqtt.unsubscribe("sensors/temperature")
```

### Status

#### `async def is_connected() -> bool`

Check if connected to MQTT broker.

**Example:**
```python
if await mqtt.is_connected():
    await mqtt.publish("status", {"online": True})
```

#### `def get_subscriptions() -> List[str]`

Get list of subscribed topics.

**Example:**
```python
topics = mqtt.get_subscriptions()
print(f"Subscribed to: {topics}")
```

#### `def get_status() -> Dict[str, Any]`

Get comprehensive plugin status.

**Example:**
```python
status = mqtt.get_status()
# {
#     'name': 'mqtt',
#     'initialized': True,
#     'connected': True,
#     'broker_host': 'localhost',
#     'broker_port': 1883,
#     'client_id': 'quickroute-abc123',
#     'subscriptions': 3,
#     'subscribed_topics': ['sensors/+', 'devices/#', 'alerts']
# }
```

## Admin Interface (Mosquitto Dynamic Security)

The MQTT plugin supports a separate admin connection for broker management via Mosquitto's Dynamic Security plugin.

### Configuration

Add admin configuration to `settings.py`:

```python
# Normal MQTT client
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "user"
MQTT_PASSWORD = "password"

# Admin interface (optional)
MQTT_ADMIN_HOST = "localhost"  # Can be same or different broker
MQTT_ADMIN_PORT = 1884  # Mosquitto dynamic security port
MQTT_ADMIN_USERNAME = "admin"
MQTT_ADMIN_PASSWORD = "admin-password"
```

### Setup Mosquitto Dynamic Security

Enable dynamic security in `mosquitto.conf`:

```conf
# Dynamic security plugin
plugin /usr/share/mosquitto/mosquitto_dynamic_security.so
plugin_opt_config_file /var/lib/mosquitto/dynamic-security.json

# Admin listener
listener 1884
allow_anonymous false

# Normal listener
listener 1883
```

Initialize dynamic security:

```bash
mosquitto_ctrl dynsec init /var/lib/mosquitto/dynamic-security.json admin admin-password
```

### Admin API

Once configured, use `mqtt.admin` for management operations:

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
mqtt = plugin_manager.get("mqtt")

# Check if admin is available
if mqtt.admin:
    # User management
    await mqtt.admin.create_user("newuser", "password")
    await mqtt.admin.delete_user("olduser")
    await mqtt.admin.set_password("user", "newpassword")
    users = await mqtt.admin.list_users()

    # ACL management
    await mqtt.admin.add_role("sensors_reader")
    await mqtt.admin.add_acl_to_role("sensors_reader", "sensors/#", "subscribe")
    await mqtt.admin.assign_role("user", "sensors_reader")

    # Client management
    await mqtt.admin.enable_client("client_id")
    await mqtt.admin.disable_client("client_id")

    # Get broker info
    clients = await mqtt.admin.get_connected_clients()
    stats = await mqtt.admin.get_broker_stats()
```

### User Management

#### Create User

```python
# Create user with password
await mqtt.admin.create_user("iot_device_001", "secure_password")

# Create user with specific client ID
await mqtt.admin.create_user(
    username="iot_device_001",
    password="secure_password",
    client_id="device_001"
)
```

#### Delete User

```python
await mqtt.admin.delete_user("old_device")
```

#### Change Password

```python
await mqtt.admin.set_password("iot_device_001", "new_password")
```

#### List Users

```python
users = await mqtt.admin.list_users()
# Returns: [{"username": "user1", "roles": ["reader"]}, ...]
```

### Role & ACL Management

#### Create Role

```python
# Create a role
await mqtt.admin.add_role("temperature_sensors")
```

#### Add ACL to Role

```python
# Read access to topic
await mqtt.admin.add_acl_to_role(
    role="temperature_sensors",
    topic="sensors/temperature/#",
    access="subscribe"
)

# Write access
await mqtt.admin.add_acl_to_role(
    role="controllers",
    topic="devices/+/commands",
    access="publish"
)

# Read and write
await mqtt.admin.add_acl_to_role(
    role="admin_role",
    topic="#",
    access="both"  # publish and subscribe
)
```

#### Assign Role to User

```python
await mqtt.admin.assign_role("iot_device_001", "temperature_sensors")

# Assign multiple roles
await mqtt.admin.assign_role("admin_user", "admin_role")
await mqtt.admin.assign_role("admin_user", "temperature_sensors")
```

#### Remove Role from User

```python
await mqtt.admin.remove_role("user", "old_role")
```

### Client Management

#### Get Connected Clients

```python
clients = await mqtt.admin.get_connected_clients()
# Returns: [
#     {"client_id": "device_001", "username": "iot_device_001", "connected_at": "..."},
#     ...
# ]
```

#### Disconnect Client

```python
# Disconnect client by client ID
await mqtt.admin.disconnect_client("device_001")
```

#### Enable/Disable Client

```python
# Disable client (prevent reconnection)
await mqtt.admin.disable_client("device_001")

# Re-enable client
await mqtt.admin.enable_client("device_001")
```

### Broker Statistics

#### Get Broker Stats

```python
stats = await mqtt.admin.get_broker_stats()
# Returns: {
#     "clients_connected": 15,
#     "clients_total": 50,
#     "messages_sent": 1234,
#     "messages_received": 5678,
#     "uptime_seconds": 86400
# }
```

#### Subscribe to $SYS Topics

For real-time broker monitoring, subscribe to `$SYS/#` topics:

```python
@mqtt.subscribe("$SYS/broker/clients/connected")
async def monitor_clients(topic: str, message: str):
    client_count = int(message)
    print(f"Connected clients: {client_count}")

@mqtt.subscribe("$SYS/broker/messages/sent")
async def monitor_messages(topic: str, message: str):
    msg_count = int(message)
    print(f"Messages sent: {msg_count}")
```

### Real-World Example

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
mqtt = plugin_manager.get("mqtt")

async def setup_iot_device(device_id: str, location: str):
    """Set up new IoT device with proper permissions."""

    if not mqtt.admin:
        raise RuntimeError("MQTT admin not configured")

    # Create user for device
    username = f"device_{device_id}"
    password = generate_secure_password()

    await mqtt.admin.create_user(username, password)

    # Create role for device location
    role_name = f"sensors_{location}"

    # Check if role exists, create if not
    roles = await mqtt.admin.list_roles()
    if role_name not in [r["name"] for r in roles]:
        await mqtt.admin.add_role(role_name)

        # Add read permission for sensors in location
        await mqtt.admin.add_acl_to_role(
            role=role_name,
            topic=f"sensors/{location}/#",
            access="publish"
        )

        # Add write permission for device commands
        await mqtt.admin.add_acl_to_role(
            role=role_name,
            topic=f"devices/{device_id}/commands",
            access="subscribe"
        )

    # Assign role to user
    await mqtt.admin.assign_role(username, role_name)

    return {
        "username": username,
        "password": password,
        "topics": {
            "publish": f"sensors/{location}/#",
            "subscribe": f"devices/{device_id}/commands"
        }
    }

# Usage
device_creds = await setup_iot_device("001", "warehouse_a")
print(f"Device credentials: {device_creds}")
```

### Admin API vs Normal Client

**Two separate connections:**

```python
mqtt = plugin_manager.get("mqtt")

# Normal client operations (port 1883)
await mqtt.publish("sensors/temp", {"value": 23.5})
await mqtt.subscribe("devices/+/status")
await mqtt.is_connected()

# Admin operations (port 1884)
if mqtt.admin:
    await mqtt.admin.create_user("user", "pass")
    await mqtt.admin.add_role("reader")
    clients = await mqtt.admin.get_connected_clients()
```

**Benefits:**
- Separate credentials for admin vs normal operations
- Admin on different port for security
- Normal client works without admin configured
- Can point admin to different broker

### Security Best Practices

1. **Use separate admin port**: Don't expose admin on public port
2. **Strong admin credentials**: Admin has full broker control
3. **Firewall admin port**: Only allow from trusted IPs
4. **Use TLS for admin**: Encrypt admin communications
5. **Audit admin actions**: Log all user/role changes
6. **Rotate admin password**: Change regularly
7. **Principle of least privilege**: Give users minimal permissions

### Troubleshooting

#### Admin not available

```python
mqtt = plugin_manager.get("mqtt")
if not mqtt.admin:
    print("Admin not configured - check MQTT_ADMIN_HOST setting")
```

#### Connection failed

- Verify Mosquitto dynamic security is enabled
- Check `mosquitto.conf` has correct listener port
- Verify admin username/password is correct
- Check firewall allows connection to admin port

#### Permission denied

- Ensure admin user has proper permissions
- Check `/var/lib/mosquitto/dynamic-security.json`
- Verify admin user was created with `mosquitto_ctrl dynsec init`

## MQTT Topics

### Topic Wildcards

MQTT supports two wildcard characters:

1. **Single-level wildcard (`+`)**: Matches one topic level
   ```python
   "sensors/+/temperature"  # Matches: sensors/room1/temperature, sensors/room2/temperature
   ```

2. **Multi-level wildcard (`#`)**: Matches multiple topic levels
   ```python
   "sensors/#"  # Matches: sensors/temp, sensors/room1/temp, sensors/room1/humidity
   ```

### Best Practices

1. **Use hierarchical topics**: `building/floor/room/device/metric`
2. **Avoid leading slashes**: Use `sensors/temp` not `/sensors/temp`
3. **Keep topics readable**: Use descriptive names
4. **Use wildcards wisely**: Too broad = performance issues

## Quality of Service (QoS)

MQTT supports three QoS levels:

- **QoS 0**: At most once (fire and forget)
- **QoS 1**: At least once (acknowledged delivery)
- **QoS 2**: Exactly once (assured delivery)

```python
# QoS 0 - Fast but unreliable
await mqtt.publish("logs/debug", message, qos=0)

# QoS 1 - Reliable, may duplicate
await mqtt.publish("sensors/data", message, qos=1)

# QoS 2 - Reliable, no duplicates (slowest)
await mqtt.publish("commands/critical", message, qos=2)
```

## Use Cases

### IoT Sensor Data Collection

```python
@mqtt.subscribe("sensors/+/temperature")
async def handle_temperature(topic: str, message: dict):
    device_id = topic.split('/')[1]
    temperature = message['value']

    # Store in database
    await store_sensor_data(device_id, 'temperature', temperature)

    # Alert if too hot
    if temperature > 30:
        await send_alert(f"High temperature: {temperature}°C")
```

### Device Control

```python
@router.post("/devices/{device_id}/turn-on")
async def turn_on_device(device_id: str):
    mqtt = plugin_manager.get("mqtt")
    await mqtt.publish(f"devices/{device_id}/commands", {"action": "turn_on"})
    return {"status": "command_sent"}
```

### Real-Time Notifications

```python
@mqtt.subscribe("alerts/#")
async def handle_alert(topic: str, message: dict):
    alert_type = topic.split('/')[-1]

    # Send to WebSocket clients
    websocket_manager = get_websocket_manager()
    await websocket_manager.broadcast(f"alert/{alert_type}", message)
```

### Inter-Service Communication

```python
# Service A publishes
await mqtt.publish("services/auth/user-logged-in", {
    "user_id": 123,
    "timestamp": "2025-11-01T12:00:00Z"
})

# Service B subscribes
@mqtt.subscribe("services/auth/#")
async def handle_auth_events(topic: str, message: dict):
    event = topic.split('/')[-1]
    if event == "user-logged-in":
        await update_user_activity(message['user_id'])
```

## Advanced Features

### Retained Messages

Retained messages are stored by the broker and sent to new subscribers:

```python
# Publish retained status
await mqtt.publish("devices/livingroom/status", {
    "online": True,
    "last_seen": "2025-11-01T12:00:00Z"
}, retain=True)

# New subscribers immediately receive the last retained message
@mqtt.subscribe("devices/+/status")
async def handle_status(topic: str, message: dict):
    # Will receive retained message immediately upon subscription
    print(f"Device status: {message}")
```

### Connection Monitoring

```python
import asyncio

async def monitor_mqtt_connection():
    """Monitor MQTT connection and reconnect if needed."""
    mqtt = plugin_manager.get("mqtt")

    while True:
        if not await mqtt.is_connected():
            logger.warning("MQTT disconnected, waiting for reconnection...")
        else:
            logger.info("MQTT connected")

        await asyncio.sleep(30)

# Start monitoring
asyncio.create_task(monitor_mqtt_connection())
```

### Message Handling Patterns

```python
# Pattern 1: Request-Response
async def send_command_and_wait(device_id: str, command: dict):
    response_topic = f"devices/{device_id}/response"
    response_received = asyncio.Event()
    response_data = {}

    @mqtt.subscribe(response_topic)
    async def handle_response(topic: str, message: dict):
        nonlocal response_data
        response_data = message
        response_received.set()

    # Send command
    await mqtt.publish(f"devices/{device_id}/commands", command)

    # Wait for response (with timeout)
    try:
        await asyncio.wait_for(response_received.wait(), timeout=5.0)
        return response_data
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    finally:
        mqtt.unsubscribe(response_topic)

# Pattern 2: Batch Processing
batch = []
batch_size = 10

@mqtt.subscribe("sensors/+/data")
async def batch_sensor_data(topic: str, message: dict):
    batch.append(message)

    if len(batch) >= batch_size:
        await process_batch(batch)
        batch.clear()

# Pattern 3: Throttling
from datetime import datetime, timedelta

last_process_time = {}

@mqtt.subscribe("sensors/+/readings")
async def throttled_handler(topic: str, message: dict):
    now = datetime.now()

    # Process at most once per second per topic
    if topic not in last_process_time or \
       now - last_process_time[topic] > timedelta(seconds=1):
        await process_reading(message)
        last_process_time[topic] = now
```

## Testing

### Unit Tests

```python
import pytest
from quickroute.plugins import get_plugin_manager

@pytest.mark.asyncio
async def test_mqtt_publish():
    mqtt = plugin_manager.get("mqtt")

    result = await mqtt.publish("test/topic", {"data": "value"})
    assert result is True

@pytest.mark.asyncio
async def test_mqtt_subscribe():
    mqtt = plugin_manager.get("mqtt")

    received_messages = []

    @mqtt.subscribe("test/topic")
    async def handler(topic, message):
        received_messages.append(message)

    await mqtt.publish("test/topic", {"test": "data"})
    await asyncio.sleep(0.1)  # Wait for message

    assert len(received_messages) == 1
    assert received_messages[0]["test"] == "data"
```

### Mock MQTT Broker for Testing

```python
# Use Eclipse Mosquitto for testing
# docker run -d -p 1883:1883 eclipse-mosquitto

# Or use HBMQTT (pure Python)
# pip install hbmqtt
```

## Troubleshooting

### Connection Issues

```python
# Check if MQTT is initialized
mqtt = plugin_manager.get("mqtt")
if not mqtt:
    print("MQTT plugin not loaded")
elif not mqtt.initialized:
    print("MQTT plugin failed to initialize")
elif not await mqtt.is_connected():
    print("MQTT not connected to broker")
```

### Message Not Received

1. Check topic subscription matches
2. Verify QoS levels
3. Check broker logs
4. Ensure callback function is async if needed

### Performance

1. Use QoS 0 for high-frequency, non-critical data
2. Batch messages when possible
3. Avoid subscribing to too many topics with wildcards
4. Monitor message queue size

## Security

### TLS/SSL (Coming Soon)

```python
MQTT_TLS_ENABLED = True
MQTT_TLS_CA_CERTS = "/path/to/ca.crt"
MQTT_TLS_CERTFILE = "/path/to/client.crt"
MQTT_TLS_KEYFILE = "/path/to/client.key"
```

### Best Practices

1. **Use strong passwords**: Generate random passwords
2. **Limit topic access**: Use broker ACLs
3. **Use TLS**: Always in production
4. **Validate messages**: Don't trust client data
5. **Rate limiting**: Prevent DoS attacks

## Resources

- [MQTT Protocol Specification](https://mqtt.org/)
- [Paho MQTT Python Client](https://github.com/eclipse/paho.mqtt.python)
- [HiveMQ MQTT Essentials](https://www.hivemq.com/mqtt-essentials/)
- [Mosquitto MQTT Broker](https://mosquitto.org/)
