# InfluxDB Plugin for QuickRoute

InfluxDB plugin for time-series data storage, metrics collection, and IoT data management.

## Installation

```bash
pip install influxdb-client
```

## Configuration

Add to your `settings.py`:

```python
# Add InfluxDB plugin
INSTALLED_PLUGINS = [
    'quickroute.plugins.influxdb',
]

# InfluxDB Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "your-influxdb-token"
INFLUXDB_ORG = "your-organization"
INFLUXDB_BUCKET = "metrics"
INFLUXDB_TIMEOUT = 10000  # milliseconds
INFLUXDB_VERIFY_SSL = True
```

## Quick Start

### 1. Writing Data Points

```python
from quickroute.plugins import get_plugin_manager

plugin_manager = get_plugin_manager(settings)
influxdb = plugin_manager.get("influxdb")

# Write single point
await influxdb.write_point(
    measurement="api_response_time",
    fields={"duration_ms": 245.5, "status_code": 200},
    tags={"endpoint": "/api/users", "method": "GET"}
)

# Write with timestamp
from datetime import datetime
await influxdb.write_point(
    measurement="temperature",
    fields={"value": 23.5, "humidity": 65.0},
    tags={"sensor_id": "sensor_001", "location": "room_a"},
    timestamp=datetime.utcnow()
)

# Batch write (efficient)
points = [
    {
        "measurement": "cpu_usage",
        "fields": {"percent": 45.2},
        "tags": {"host": "server1"}
    },
    {
        "measurement": "memory_usage",
        "fields": {"percent": 78.5},
        "tags": {"host": "server1"}
    }
]
await influxdb.write_points(points)
```

### 2. Querying Data

```python
# Simple query
result = await influxdb.query('''
    from(bucket: "metrics")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "api_response_time")
        |> mean()
''')

# Query with parameters
result = await influxdb.query_range(
    measurement="temperature",
    start="-24h",
    stop="now()",
    filters={"sensor_id": "sensor_001"}
)

# Aggregation
result = await influxdb.query('''
    from(bucket: "metrics")
        |> range(start: -7d)
        |> filter(fn: (r) => r._measurement == "sales")
        |> aggregateWindow(every: 1d, fn: sum)
''')
```

### 3. Using in Routes

```python
from fastapi import APIRouter
from quickroute.plugins import get_plugin_manager
from quickroute import settings
from datetime import datetime

router = APIRouter()

@router.post("/metrics/track")
async def track_metric(metric: dict):
    """Track custom application metric."""
    plugin_manager = get_plugin_manager(settings)
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="custom_metrics",
            fields={"value": metric["value"]},
            tags={"metric_name": metric["name"], "user_id": metric.get("user_id")}
        )
        return {"status": "tracked"}
    else:
        return {"status": "error", "message": "InfluxDB not available"}

@router.get("/metrics/api-performance")
async def get_api_performance():
    """Get API performance metrics for last 24 hours."""
    plugin_manager = get_plugin_manager(settings)
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        result = await influxdb.query('''
            from(bucket: "metrics")
                |> range(start: -24h)
                |> filter(fn: (r) => r._measurement == "api_response_time")
                |> group(columns: ["endpoint"])
                |> mean(column: "_value")
        ''')
        return {"data": result}
    else:
        return {"status": "error", "message": "InfluxDB not available"}
```

## InfluxDB ORM (Django-Style Models)

QuickRoute provides a Django-like ORM abstraction for InfluxDB, making time-series data feel like regular models.

### Defining Models

```python
from quickroute.influxdb import InfluxModel, Field, Tag

class Temperature(InfluxModel):
    """Temperature sensor readings."""

    # Measurement name
    measurement = "sensor_temperature"

    # Fields (actual data - not indexed)
    value: float = Field()
    humidity: float = Field()
    battery_percent: float = Field(default=100.0)

    # Tags (indexed metadata)
    sensor_id: str = Tag()
    location: str = Tag()
    sensor_type: str = Tag(default="generic")

class APIMetric(InfluxModel):
    """API performance metrics."""

    measurement = "api_metrics"

    # Fields
    duration_ms: float = Field()
    status_code: int = Field()
    error_count: int = Field(default=0)

    # Tags
    endpoint: str = Tag()
    method: str = Tag()
    environment: str = Tag(default="production")

class Revenue(InfluxModel):
    """Revenue tracking."""

    measurement = "revenue"

    # Fields
    amount: float = Field()
    amount_usd: float = Field()

    # Tags
    currency: str = Tag()
    product: str = Tag()
    payment_method: str = Tag()
```

### Creating and Saving

```python
# Create instance
temp = Temperature(
    value=23.5,
    humidity=65.0,
    sensor_id="sensor_001",
    location="room_a"
)

# Save to InfluxDB
await temp.save()

# Save with custom timestamp
from datetime import datetime
await temp.save(timestamp=datetime.utcnow())

# Batch create
temps = [
    Temperature(value=23.5, humidity=65.0, sensor_id="001", location="room_a"),
    Temperature(value=24.1, humidity=62.0, sensor_id="002", location="room_b"),
    Temperature(value=22.8, humidity=68.0, sensor_id="003", location="room_c"),
]
await Temperature.objects.bulk_create(temps)
```

### Querying

```python
# Get all data from last hour
temps = await Temperature.objects.range("-1h").all()

# Filter by tags
room_a_temps = await Temperature.objects.filter(location="room_a").range("-24h").all()

# Multiple filters
outdoor_temps = await Temperature.objects.filter(
    sensor_type="outdoor",
    location="garden"
).range("-7d").all()

# Get single record
latest = await Temperature.objects.filter(sensor_id="001").latest()

# Check if exists
exists = await Temperature.objects.filter(sensor_id="001").exists()
```

### Aggregations

```python
# Mean
avg_temp = await Temperature.objects.filter(location="room_a").range("-1h").mean("value")

# Sum
total_revenue = await Revenue.objects.filter(currency="USD").range("-30d").sum("amount")

# Count
error_count = await APIMetric.objects.filter(status_code__gte=400).range("-1h").count()

# Min/Max
min_temp = await Temperature.objects.range("-24h").min("value")
max_temp = await Temperature.objects.range("-24h").max("value")

# Multiple aggregations
stats = await Temperature.objects.filter(sensor_id="001").range("-1h").aggregate(
    avg_value=("value", "mean"),
    avg_humidity=("humidity", "mean"),
    min_value=("value", "min"),
    max_value=("value", "max")
)
# Returns: {"avg_value": 23.5, "avg_humidity": 65.0, "min_value": 20.1, "max_value": 26.3}
```

### Time Windows

```python
# Average per 5 minutes
temps_5m = await Temperature.objects.filter(sensor_id="001").range("-1h").window("5m", "mean")

# Sum per hour
hourly_revenue = await Revenue.objects.range("-7d").window("1h", "sum", field="amount")

# Count per day
daily_errors = await APIMetric.objects.filter(status_code__gte=500).range("-30d").window("1d", "count")
```

### Grouping

```python
# Group by tag
by_location = await Temperature.objects.range("-1h").group_by("location").mean("value")
# Returns: [{"location": "room_a", "mean": 23.5}, {"location": "room_b", "mean": 24.1}]

# Group by multiple tags
by_sensor = await Temperature.objects.range("-24h").group_by("location", "sensor_type").mean("value")
```

### Chaining Queries

```python
# Build complex queries
query = (
    Temperature.objects
    .filter(location="room_a")
    .range("-7d")
    .window("1h", "mean")
    .limit(100)
)
results = await query.all()

# Conditional filtering
query = Temperature.objects.range("-1h")

if sensor_id:
    query = query.filter(sensor_id=sensor_id)

if location:
    query = query.filter(location=location)

results = await query.all()
```

### Advanced Filtering

```python
# Comparison operators
high_temps = await Temperature.objects.filter(value__gte=25.0).range("-1h").all()

low_battery = await Temperature.objects.filter(battery_percent__lt=20.0).range("-24h").all()

# Range
normal_temps = await Temperature.objects.filter(
    value__gte=18.0,
    value__lte=26.0
).range("-1h").all()

# In list
selected_sensors = await Temperature.objects.filter(
    sensor_id__in=["001", "002", "003"]
).range("-1h").all()
```

### Deleting Data

```python
# Delete specific data
await Temperature.objects.filter(sensor_id="old_sensor").range("-365d", "-30d").delete()

# Delete all data for measurement
await Temperature.objects.range("-1y", "now()").delete()
```

### Manager Methods

```python
class Temperature(InfluxModel):
    measurement = "sensor_temperature"

    value: float = Field()
    sensor_id: str = Tag()
    location: str = Tag()

    class Meta:
        bucket = "sensors"  # Override default bucket

    # Custom manager
    class objects(InfluxManager):
        async def get_latest_by_sensor(self, sensor_id: str):
            """Get latest reading for sensor."""
            return await self.filter(sensor_id=sensor_id).latest()

        async def get_daily_average(self, location: str, days: int = 7):
            """Get daily average for location."""
            return await (
                self.filter(location=location)
                .range(f"-{days}d")
                .window("1d", "mean", field="value")
            )

# Usage
latest = await Temperature.objects.get_latest_by_sensor("001")
daily_avg = await Temperature.objects.get_daily_average("room_a", days=30)
```

### Real-World Examples

#### 1. IoT Temperature Monitoring

```python
class SensorReading(InfluxModel):
    measurement = "sensor_readings"

    temperature: float = Field()
    humidity: float = Field()
    pressure: float = Field(default=None)
    battery: float = Field()

    sensor_id: str = Tag()
    location: str = Tag()
    sensor_type: str = Tag()

# Collect data
async def collect_sensor_data(sensor_id: str, data: dict):
    reading = SensorReading(
        temperature=data["temp"],
        humidity=data["humidity"],
        pressure=data.get("pressure"),
        battery=data["battery"],
        sensor_id=sensor_id,
        location=data["location"],
        sensor_type=data["type"]
    )
    await reading.save()

# Get hourly averages
hourly_temps = await SensorReading.objects.filter(
    sensor_id="001"
).range("-24h").window("1h", "mean", field="temperature")

# Low battery alert
low_battery_sensors = await SensorReading.objects.filter(
    battery__lt=20.0
).range("-1h").group_by("sensor_id").all()
```

#### 2. API Performance Tracking

```python
class APICall(InfluxModel):
    measurement = "api_calls"

    duration_ms: float = Field()
    status_code: int = Field()

    endpoint: str = Tag()
    method: str = Tag()
    user_id: str = Tag(default="anonymous")

# Track API call
async def track_api_call(endpoint: str, method: str, duration: float, status: int):
    call = APICall(
        duration_ms=duration,
        status_code=status,
        endpoint=endpoint,
        method=method
    )
    await call.save()

# Get slow endpoints
slow_endpoints = await APICall.objects.filter(
    duration_ms__gte=1000.0
).range("-1h").group_by("endpoint").count()

# Error rate by endpoint
error_rate = await APICall.objects.filter(
    status_code__gte=400
).range("-24h").group_by("endpoint", "status_code").count()
```

#### 3. Business Metrics

```python
class UserActivity(InfluxModel):
    measurement = "user_activity"

    action_count: int = Field(default=1)

    user_id: str = Tag()
    action_type: str = Tag()
    source: str = Tag()

class OrderMetric(InfluxModel):
    measurement = "orders"

    amount: float = Field()
    item_count: int = Field()

    product: str = Tag()
    status: str = Tag()
    payment_method: str = Tag()

# Track user signup
async def track_signup(user_id: int, source: str):
    activity = UserActivity(
        user_id=str(user_id),
        action_type="signup",
        source=source
    )
    await activity.save()

# Get daily signups by source
daily_signups = await UserActivity.objects.filter(
    action_type="signup"
).range("-30d").group_by("source").window("1d", "sum", field="action_count")

# Total revenue by product
revenue_by_product = await OrderMetric.objects.filter(
    status="completed"
).range("-30d").group_by("product").sum("amount")
```

### Model Meta Options

```python
class Temperature(InfluxModel):
    measurement = "sensor_temperature"

    value: float = Field()
    sensor_id: str = Tag()

    class Meta:
        bucket = "sensors"  # Override default bucket
        ordering = ["-_time"]  # Default ordering
        default_range = "-1h"  # Default time range for queries
```

### Field Types

```python
from quickroute.influxdb import Field, Tag

class MyModel(InfluxModel):
    # Numeric fields
    count: int = Field()
    value: float = Field()

    # String fields (stored as string in InfluxDB)
    message: str = Field()

    # Boolean fields
    is_active: bool = Field(default=True)

    # Optional fields
    optional_value: float = Field(default=None)

    # Tags (always strings, indexed)
    category: str = Tag()
    status: str = Tag(default="active")
```

### Query API Reference

```python
# Range
.range("-1h")  # Last hour
.range("-24h", "now()")  # Last 24 hours
.range("2025-11-01T00:00:00Z", "2025-11-01T23:59:59Z")  # Specific range

# Filter
.filter(sensor_id="001")
.filter(sensor_id="001", location="room_a")
.filter(value__gte=25.0)  # Greater than or equal
.filter(value__lt=10.0)   # Less than
.filter(sensor_id__in=["001", "002"])  # In list

# Aggregations
.mean("field_name")
.sum("field_name")
.count()
.min("field_name")
.max("field_name")
.median("field_name")
.stddev("field_name")

# Windows
.window("5m", "mean")  # 5 minute windows, mean
.window("1h", "sum", field="amount")  # 1 hour windows, sum specific field

# Grouping
.group_by("tag_name")
.group_by("tag1", "tag2")

# Limiting
.limit(100)
.first()  # Get first result
.latest()  # Get latest result

# Execution
.all()  # Get all results
.exists()  # Check if any results exist
.count()  # Count results
```

### Comparison with Raw API

**Without ORM (raw):**
```python
await influxdb.write_point(
    measurement="sensor_temperature",
    fields={"value": 23.5, "humidity": 65.0},
    tags={"sensor_id": "001", "location": "room_a"}
)

result = await influxdb.query('''
    from(bucket: "metrics")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "sensor_temperature")
        |> filter(fn: (r) => r.sensor_id == "001")
        |> mean(column: "_value")
''')
```

**With ORM (clean):**
```python
temp = Temperature(value=23.5, humidity=65.0, sensor_id="001", location="room_a")
await temp.save()

avg = await Temperature.objects.filter(sensor_id="001").range("-1h").mean("value")
```

### Benefits of ORM

1. **Type Safety**: Python type hints catch errors early
2. **Auto-completion**: IDE knows your fields and tags
3. **Less Boilerplate**: No manual point construction
4. **Readable Queries**: Django-like syntax vs Flux
5. **Validation**: Field validation before writing
6. **Reusable**: Define once, use everywhere
7. **Testable**: Easy to mock and test

## API Reference

### Writing Data

#### `async def write_point(measurement: str, fields: dict, tags: dict = None, timestamp: datetime = None) -> bool`

Write a single data point to InfluxDB.

**Parameters:**
- `measurement` (str): Measurement name (like a table name)
- `fields` (dict): Field values (actual data, e.g., `{"temperature": 23.5}`)
- `tags` (dict, optional): Tag values (indexed metadata, e.g., `{"sensor_id": "001"}`)
- `timestamp` (datetime, optional): Point timestamp (defaults to now)

**Returns:**
- `bool`: True if written successfully

**Example:**
```python
await influxdb.write_point(
    measurement="sensor_data",
    fields={"temperature": 23.5, "humidity": 65.0},
    tags={"sensor_id": "001", "location": "room_a"}
)
```

#### `async def write_points(points: List[dict]) -> bool`

Write multiple data points in batch (more efficient).

**Parameters:**
- `points` (List[dict]): List of point dictionaries with keys: measurement, fields, tags, timestamp

**Returns:**
- `bool`: True if written successfully

**Example:**
```python
points = [
    {
        "measurement": "cpu",
        "fields": {"usage": 45.2},
        "tags": {"host": "server1"},
        "timestamp": datetime.utcnow()
    },
    {
        "measurement": "memory",
        "fields": {"usage": 78.5},
        "tags": {"host": "server1"},
        "timestamp": datetime.utcnow()
    }
]
await influxdb.write_points(points)
```

### Querying Data

#### `async def query(flux_query: str) -> List[dict]`

Execute a Flux query and return results.

**Parameters:**
- `flux_query` (str): Flux query language string

**Returns:**
- `List[dict]`: Query results as list of dictionaries

**Example:**
```python
result = await influxdb.query('''
    from(bucket: "metrics")
        |> range(start: -1h)
        |> filter(fn: (r) => r._measurement == "temperature")
        |> mean()
''')
```

#### `async def query_range(measurement: str, start: str, stop: str = "now()", filters: dict = None, fields: List[str] = None) -> List[dict]`

Simple time range query helper (no Flux needed).

**Parameters:**
- `measurement` (str): Measurement name
- `start` (str): Start time (e.g., "-1h", "-24h", "2025-11-01T00:00:00Z")
- `stop` (str): End time (default: "now()")
- `filters` (dict, optional): Tag filters (e.g., `{"sensor_id": "001"}`)
- `fields` (List[str], optional): Specific fields to retrieve

**Returns:**
- `List[dict]`: Query results

**Example:**
```python
# Last hour of data
result = await influxdb.query_range(
    measurement="temperature",
    start="-1h",
    filters={"sensor_id": "001"}
)

# Specific time range
result = await influxdb.query_range(
    measurement="sales",
    start="2025-11-01T00:00:00Z",
    stop="2025-11-01T23:59:59Z",
    fields=["amount", "quantity"]
)
```

### Utilities

#### `async def delete_measurement(measurement: str, start: str, stop: str) -> bool`

Delete data for a measurement within time range.

**Parameters:**
- `measurement` (str): Measurement name
- `start` (str): Start time
- `stop` (str): End time

**Example:**
```python
# Delete old data
await influxdb.delete_measurement("old_metrics", "-365d", "now()")
```

#### `async def bucket_exists(bucket: str) -> bool`

Check if a bucket exists.

**Example:**
```python
if not await influxdb.bucket_exists("new_metrics"):
    await influxdb.create_bucket("new_metrics", retention_days=30)
```

#### `async def create_bucket(bucket: str, retention_days: int = None) -> bool`

Create a new bucket.

**Parameters:**
- `bucket` (str): Bucket name
- `retention_days` (int, optional): Data retention period in days

**Example:**
```python
await influxdb.create_bucket("metrics", retention_days=90)
```

## Data Model

### Measurements

Think of measurements as "tables" - they group related data:
```python
measurement="api_response_time"
measurement="sensor_temperature"
measurement="user_signups"
```

### Fields

Actual data values (not indexed):
```python
fields={
    "duration_ms": 245.5,
    "status_code": 200,
    "error_count": 0
}
```

### Tags

Indexed metadata for filtering (indexed):
```python
tags={
    "endpoint": "/api/users",
    "method": "GET",
    "region": "us-east-1",
    "environment": "production"
}
```

**Best Practice:**
- Use **tags** for dimensions you'll filter/group by (indexed)
- Use **fields** for actual measurements (not indexed)

## Use Cases

### 1. API Performance Monitoring

```python
# Middleware to track API performance
from fastapi import Request
import time

@app.middleware("http")
async def track_api_performance(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Write to InfluxDB
    influxdb = plugin_manager.get("influxdb")
    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="api_response_time",
            fields={
                "duration_ms": duration_ms,
                "status_code": response.status_code
            },
            tags={
                "endpoint": request.url.path,
                "method": request.method,
                "host": request.client.host
            }
        )

    return response
```

### 2. Error Rate Tracking

```python
async def track_error(error_type: str, error_message: str, user_id: str = None):
    """Track application errors."""
    influxdb = plugin_manager.get("influxdb")
    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="application_errors",
            fields={
                "count": 1,
                "message": error_message[:200]  # Truncate
            },
            tags={
                "error_type": error_type,
                "user_id": user_id or "anonymous",
                "environment": settings.ENVIRONMENT
            }
        )
```

### 3. IoT Sensor Data Collection

```python
@router.post("/sensors/{sensor_id}/data")
async def collect_sensor_data(sensor_id: str, data: dict):
    """Collect IoT sensor data."""
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="sensor_readings",
            fields={
                "temperature": data["temperature"],
                "humidity": data["humidity"],
                "pressure": data.get("pressure"),
                "battery": data.get("battery_percent")
            },
            tags={
                "sensor_id": sensor_id,
                "location": data.get("location", "unknown"),
                "type": data.get("sensor_type", "generic")
            }
        )
        return {"status": "collected"}

    return {"status": "error"}
```

### 4. Business Metrics

```python
async def track_user_signup(user_id: int, plan: str, source: str):
    """Track user signup metrics."""
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="user_signups",
            fields={
                "count": 1,
                "user_id": user_id
            },
            tags={
                "plan": plan,
                "source": source,
                "country": get_user_country()
            }
        )

async def track_revenue(amount: float, currency: str, product: str):
    """Track revenue metrics."""
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        await influxdb.write_point(
            measurement="revenue",
            fields={
                "amount": amount,
                "amount_usd": convert_to_usd(amount, currency)
            },
            tags={
                "currency": currency,
                "product": product,
                "payment_method": "stripe"
            }
        )
```

### 5. System Monitoring

```python
import psutil
from datetime import datetime

async def collect_system_metrics():
    """Collect system metrics every minute."""
    influxdb = plugin_manager.get("influxdb")

    if influxdb and influxdb.initialized:
        # CPU metrics
        await influxdb.write_point(
            measurement="system_cpu",
            fields={
                "usage_percent": psutil.cpu_percent(),
                "load_1m": psutil.getloadavg()[0],
                "load_5m": psutil.getloadavg()[1]
            },
            tags={
                "host": socket.gethostname(),
                "environment": settings.ENVIRONMENT
            }
        )

        # Memory metrics
        memory = psutil.virtual_memory()
        await influxdb.write_point(
            measurement="system_memory",
            fields={
                "usage_percent": memory.percent,
                "available_mb": memory.available / 1024 / 1024,
                "used_mb": memory.used / 1024 / 1024
            },
            tags={
                "host": socket.gethostname()
            }
        )

# Schedule with jobs system
from quickroute import periodic

@periodic("1m")
async def monitor_system():
    await collect_system_metrics()
```

## Flux Query Language Basics

### Simple Queries

```flux
// Get last hour of data
from(bucket: "metrics")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "temperature")

// Filter by tags
from(bucket: "metrics")
    |> range(start: -24h)
    |> filter(fn: (r) => r._measurement == "api_response_time")
    |> filter(fn: (r) => r.endpoint == "/api/users")
```

### Aggregations

```flux
// Average
from(bucket: "metrics")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "temperature")
    |> mean()

// Sum
from(bucket: "metrics")
    |> range(start: -24h)
    |> filter(fn: (r) => r._measurement == "sales")
    |> sum()

// Count
from(bucket: "metrics")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "errors")
    |> count()
```

### Windowing

```flux
// Average per 5 minutes
from(bucket: "metrics")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "cpu_usage")
    |> aggregateWindow(every: 5m, fn: mean)

// Sum per day
from(bucket: "metrics")
    |> range(start: -30d)
    |> filter(fn: (r) => r._measurement == "revenue")
    |> aggregateWindow(every: 1d, fn: sum)
```

### Grouping

```flux
// Group by tag
from(bucket: "metrics")
    |> range(start: -24h)
    |> filter(fn: (r) => r._measurement == "api_response_time")
    |> group(columns: ["endpoint"])
    |> mean()
```

## Performance Best Practices

### 1. Batch Writes

**Don't do this:**
```python
for sensor_reading in readings:
    await influxdb.write_point(...)  # 100 writes
```

**Do this:**
```python
points = [
    {
        "measurement": "sensor_data",
        "fields": reading["fields"],
        "tags": reading["tags"]
    }
    for reading in readings
]
await influxdb.write_points(points)  # 1 batch write
```

### 2. Use Tags Wisely

Tags are indexed - good for filtering, but don't overuse:

**Good:**
```python
tags={
    "sensor_id": "001",
    "location": "room_a",
    "type": "temperature"
}
```

**Bad (too many unique values):**
```python
tags={
    "user_id": "12345",  # High cardinality!
    "session_id": "abc-123-def",  # Changes every session!
    "timestamp_string": "2025-11-01 12:34:56"  # Don't do this!
}
```

### 3. Design Good Measurements

Group related metrics:

**Good:**
```python
measurement="api_metrics"
fields={"response_time_ms": 245, "error_count": 0}
tags={"endpoint": "/api/users", "method": "GET"}
```

**Bad:**
```python
measurement="api_users_get_response_time"  # Too specific
```

### 4. Set Retention Policies

Don't keep data forever:

```python
# 30 days for detailed metrics
await influxdb.create_bucket("metrics_detailed", retention_days=30)

# 365 days for aggregated metrics
await influxdb.create_bucket("metrics_aggregated", retention_days=365)
```

## Testing

### Unit Tests

```python
import pytest
from quickroute.plugins import get_plugin_manager

@pytest.mark.asyncio
async def test_influxdb_write_point():
    influxdb = plugin_manager.get("influxdb")

    result = await influxdb.write_point(
        measurement="test_metric",
        fields={"value": 123.45},
        tags={"test": "true"}
    )
    assert result is True

@pytest.mark.asyncio
async def test_influxdb_query():
    influxdb = plugin_manager.get("influxdb")

    # Write test data
    await influxdb.write_point(
        measurement="test_data",
        fields={"value": 100},
        tags={"test_id": "query_test"}
    )

    # Query it back
    result = await influxdb.query_range(
        measurement="test_data",
        start="-1m",
        filters={"test_id": "query_test"}
    )

    assert len(result) > 0
    assert result[0]["_value"] == 100
```

### Mock InfluxDB for Testing

```python
# Use InfluxDB Docker for testing
# docker run -d -p 8086:8086 influxdb:2.0

# Or mock for unit tests
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_influxdb():
    influxdb = MagicMock()
    influxdb.write_point = AsyncMock(return_value=True)
    influxdb.query = AsyncMock(return_value=[{"_value": 123}])
    return influxdb
```

## Dashboards and Visualization

### Grafana Integration

InfluxDB works great with Grafana for visualization:

1. Add InfluxDB data source in Grafana
2. Use Flux queries in panels
3. Create dashboards for:
   - API performance metrics
   - Error rates
   - System monitoring
   - Business metrics

**Example Grafana Query:**
```flux
from(bucket: "metrics")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r._measurement == "api_response_time")
    |> aggregateWindow(every: v.windowPeriod, fn: mean)
```

## Troubleshooting

### Connection Issues

```python
# Check if InfluxDB is initialized
influxdb = plugin_manager.get("influxdb")
if not influxdb:
    print("InfluxDB plugin not loaded")
elif not influxdb.initialized:
    print("InfluxDB plugin failed to initialize")
    print("Check INFLUXDB_URL and INFLUXDB_TOKEN")
```

### Write Failures

- Check bucket exists
- Verify token has write permissions
- Check data types (fields must be numeric, bool, or string)
- Verify timestamp format

### Query Errors

- Test queries in InfluxDB UI first
- Check bucket name is correct
- Verify time range format
- Use `|> yield()` at end of complex queries

## Security

### Best Practices

1. **Use tokens, not user/password**: Tokens are more secure
2. **Limit token permissions**: Read/write only specific buckets
3. **Use HTTPS**: Always in production (`https://influxdb.example.com`)
4. **Rotate tokens regularly**: Create new tokens periodically
5. **Don't log sensitive data**: Be careful with field values

### Token Permissions

Create tokens with minimal permissions:

```bash
# Read-only token for queries
influx auth create \
    --org myorg \
    --read-bucket metrics \
    --description "QuickRoute read-only"

# Write-only token for metrics
influx auth create \
    --org myorg \
    --write-bucket metrics \
    --description "QuickRoute write-only"
```

## Resources

- [InfluxDB Documentation](https://docs.influxdata.com/)
- [Flux Query Language](https://docs.influxdata.com/flux/)
- [Python Client](https://github.com/influxdata/influxdb-client-python)
- [Grafana with InfluxDB](https://grafana.com/docs/grafana/latest/datasources/influxdb/)
