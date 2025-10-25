"""
Example user plugin for QuickRoute.

Demonstrates how users can create their own plugins.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from ..base import BasePlugin
from ...logging import logger


class UserPlugin(BasePlugin):
    """
    Example user plugin for demonstration.

    Users can create plugins like this to add custom functionality
    to their QuickRoute applications.
    """

    @property
    def name(self) -> str:
        return "user_example"

    @property
    def description(self) -> str:
        return "Example user plugin for demonstration"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, settings):
        super().__init__(settings)
        self.custom_data = {}
        self.start_time = None

    def is_available(self) -> bool:
        """Check if plugin dependencies are available."""
        # This plugin has no external dependencies
        return True

    def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            self.start_time = datetime.utcnow()
            self.custom_data = {
                'initialized_at': self.start_time.isoformat(),
                'user_count': 0,
                'feature_flags': ['demo', 'example']
            }

            # Example: Set up any required resources
            logger.info(f"User plugin initialized at {self.start_time}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize user plugin: {e}")
            return False

    def shutdown(self):
        """Cleanup and shutdown the plugin."""
        if self.enabled:
            self.custom_data = {}
            self.start_time = None
            logger.info("User plugin shutdown")

    def add_user(self, user_id: int, user_data: Dict[str, Any]):
        """Example plugin method."""
        if self.enabled:
            self.custom_data[f'user_{user_id}'] = user_data
            self.custom_data['user_count'] = len([k for k in self.custom_data.keys() if k.startswith('user_')])
            logger.info(f"Added user {user_id} to plugin")

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Example plugin method."""
        if self.enabled:
            return self.custom_data.get(f'user_{user_id}')
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        if not self.enabled:
            return {'enabled': False}

        uptime = None
        if self.start_time:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            'enabled': True,
            'uptime_seconds': uptime,
            'user_count': self.custom_data.get('user_count', 0),
            'feature_flags': self.custom_data.get('feature_flags', []),
            'initialized_at': self.custom_data.get('initialized_at')
        }

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive plugin status."""
        base_status = super().get_status()
        base_status.update(self.get_stats())
        return base_status


# Example of how to register a custom plugin
def register_user_plugin(settings):
    """Helper function to register the user plugin."""
    from ..base import register_plugin
    plugin = UserPlugin(settings)
    register_plugin(plugin, settings)
    return plugin