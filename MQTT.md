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
