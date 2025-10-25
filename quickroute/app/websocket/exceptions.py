"""
WebSocket exceptions for QuickRoute.
"""


class WebSocketException(Exception):
    """Base WebSocket exception."""
    pass


class WebSocketDisconnect(WebSocketException):
    """WebSocket disconnect exception."""

    def __init__(self, code: int = 1000, reason: str = "Normal closure"):
        self.code = code
        self.reason = reason
        super().__init__(f"WebSocket disconnect: {code} - {reason}")


class WebSocketAuthError(WebSocketException):
    """WebSocket authentication error."""
    pass


class WebSocketRoomError(WebSocketException):
    """WebSocket room management error."""
    pass


class WebSocketMessageError(WebSocketException):
    """WebSocket message handling error."""
    pass