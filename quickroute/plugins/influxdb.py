"""
InfluxDB plugin for QuickRoute.

Provides InfluxDB integration for time-series data storage and querying.
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
from .base import BasePlugin
from quickroute.logging import logger


class InfluxDBPlugin(BasePlugin):
    """InfluxDB plugin for time-series data storage."""

    name = "influxdb"
    version = "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.client = None
        self.write_api = None
        self.query_api = None
        self._url = None
        self._org = None
        self._bucket = None

    def is_available(self) -> bool:
        """Check if influxdb-client is installed."""
        try:
            import influxdb_client

            return True
        except ImportError:
            logger.debug("influxdb-client not available")
            return False

    def initialize(self) -> bool:
        """Initialize InfluxDB client."""
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS

            self._url = getattr(self.settings, "INFLUXDB_URL", "http://localhost:8086")
            token = getattr(self.settings, "INFLUXDB_TOKEN")
            self._org = getattr(self.settings, "INFLUXDB_ORG")
            self._bucket = getattr(self.settings, "INFLUXDB_BUCKET", "metrics")
            timeout = getattr(self.settings, "INFLUXDB_TIMEOUT", 10000)
            verify_ssl = getattr(self.settings, "INFLUXDB_VERIFY_SSL", True)

            self.client = InfluxDBClient(
                url=self._url, token=token, org=self._org, timeout=timeout, verify_ssl=verify_ssl
            )

            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()

            try:
                health = self.client.health()
                if health.status == "pass":
                    logger.info(f"InfluxDB connected: {self._url} (org: {self._org})")
                    return True
                else:
                    logger.error(f"InfluxDB health check failed: {health.message}")
                    return False
            except Exception as e:
                logger.error(f"InfluxDB connection test failed: {e}")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize InfluxDB plugin: {e}")
            return False

    def shutdown(self):
        """Close InfluxDB client."""
        if self.client:
            try:
                self.client.close()
                logger.info("InfluxDB client closed")
            except Exception as e:
                logger.error(f"Error closing InfluxDB client: {e}")

    async def write_point(
        self,
        measurement: str,
        fields: Dict[str, Any],
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
        bucket: Optional[str] = None,
    ) -> bool:
        """Write a single data point to InfluxDB."""
        if not self.initialized or not self.write_api:
            logger.error("InfluxDB plugin not initialized")
            return False

        try:
            from influxdb_client import Point

            point = Point(measurement)

            for field_name, field_value in fields.items():
                point = point.field(field_name, field_value)

            if tags:
                for tag_name, tag_value in tags.items():
                    point = point.tag(tag_name, str(tag_value))

            if timestamp:
                point = point.time(timestamp)

            bucket_name = bucket or self._bucket
            self.write_api.write(bucket=bucket_name, org=self._org, record=point)

            logger.debug(f"InfluxDB wrote point to {measurement}")
            return True

        except Exception as e:
            logger.error(f"Error writing InfluxDB point: {e}")
            return False

    async def write_points(
        self, points: List[Dict[str, Any]], bucket: Optional[str] = None
    ) -> bool:
        """Write multiple data points in batch."""
        if not self.initialized or not self.write_api:
            logger.error("InfluxDB plugin not initialized")
            return False

        try:
            from influxdb_client import Point

            influx_points = []
            for point_data in points:
                point = Point(point_data["measurement"])

                for field_name, field_value in point_data["fields"].items():
                    point = point.field(field_name, field_value)

                if "tags" in point_data:
                    for tag_name, tag_value in point_data["tags"].items():
                        point = point.tag(tag_name, str(tag_value))

                if "timestamp" in point_data:
                    point = point.time(point_data["timestamp"])

                influx_points.append(point)

            bucket_name = bucket or self._bucket
            self.write_api.write(bucket=bucket_name, org=self._org, record=influx_points)

            logger.debug(f"InfluxDB wrote {len(influx_points)} points")
            return True

        except Exception as e:
            logger.error(f"Error writing InfluxDB points: {e}")
            return False

    async def query(self, flux_query: str) -> List[Dict[str, Any]]:
        """Execute a Flux query."""
        if not self.initialized or not self.query_api:
            logger.error("InfluxDB plugin not initialized")
            return []

        try:
            tables = self.query_api.query(flux_query, org=self._org)

            results = []
            for table in tables:
                for record in table.records:
                    results.append(record.values)

            logger.debug(f"InfluxDB query returned {len(results)} records")
            return results

        except Exception as e:
            logger.error(f"Error executing InfluxDB query: {e}")
            return []

    async def query_range(
        self,
        measurement: str,
        start: str,
        stop: str = "now()",
        filters: Optional[Dict[str, str]] = None,
        fields: Optional[List[str]] = None,
        bucket: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Simple time range query helper."""
        bucket_name = bucket or self._bucket

        query = f'from(bucket: "{bucket_name}")\n'
        query += f"  |> range(start: {start}, stop: {stop})\n"
        query += f'  |> filter(fn: (r) => r._measurement == "{measurement}")\n'

        if filters:
            for tag_name, tag_value in filters.items():
                query += f'  |> filter(fn: (r) => r.{tag_name} == "{tag_value}")\n'

        if fields:
            field_conditions = " or ".join([f'r._field == "{f}"' for f in fields])
            query += f"  |> filter(fn: (r) => {field_conditions})\n"

        return await self.query(query)

    async def delete_measurement(
        self, measurement: str, start: str, stop: str, bucket: Optional[str] = None
    ) -> bool:
        """Delete data for a measurement within time range."""
        if not self.initialized or not self.client:
            logger.error("InfluxDB plugin not initialized")
            return False

        try:
            bucket_name = bucket or self._bucket
            delete_api = self.client.delete_api()

            predicate = f'_measurement="{measurement}"'
            delete_api.delete(start, stop, predicate, bucket=bucket_name, org=self._org)

            logger.info(f"InfluxDB deleted {measurement} data from {start} to {stop}")
            return True

        except Exception as e:
            logger.error(f"Error deleting InfluxDB data: {e}")
            return False

    async def bucket_exists(self, bucket: str) -> bool:
        """Check if a bucket exists."""
        if not self.initialized or not self.client:
            return False

        try:
            buckets_api = self.client.buckets_api()
            bucket_obj = buckets_api.find_bucket_by_name(bucket)
            return bucket_obj is not None

        except Exception as e:
            logger.error(f"Error checking InfluxDB bucket: {e}")
            return False

    async def create_bucket(self, bucket: str, retention_days: Optional[int] = None) -> bool:
        """Create a new bucket."""
        if not self.initialized or not self.client:
            logger.error("InfluxDB plugin not initialized")
            return False

        try:
            from influxdb_client import BucketRetentionRules

            buckets_api = self.client.buckets_api()

            retention_rules = []
            if retention_days:
                retention_rules.append(
                    BucketRetentionRules(type="expire", every_seconds=retention_days * 86400)
                )

            buckets_api.create_bucket(
                bucket_name=bucket, org=self._org, retention_rules=retention_rules
            )

            logger.info(f"InfluxDB bucket created: {bucket}")
            return True

        except Exception as e:
            logger.error(f"Error creating InfluxDB bucket: {e}")
            return False


# Export for plugin discovery
Plugin = InfluxDBPlugin

__all__ = ["Plugin", "InfluxDBPlugin"]
