"""
MQTT plugin for QuickRoute.

Convention: exports 'Plugin' class.
"""

from ..app.plugins.mqtt_plugin import MQTTPlugin

Plugin = MQTTPlugin

__all__ = ['Plugin', 'MQTTPlugin']
