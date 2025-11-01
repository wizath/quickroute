"""
InfluxDB plugin for QuickRoute.

Convention: exports 'Plugin' class.
"""

from quickroute.app.plugins.influxdb_plugin import InfluxDBPlugin

Plugin = InfluxDBPlugin

__all__ = ["Plugin", "InfluxDBPlugin"]
