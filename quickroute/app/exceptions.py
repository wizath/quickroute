from fastapi import status
from typing import Any, Dict, Optional


class QuickRouteException(Exception):
    """Base exception class for QuickRoute application"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(QuickRouteException):
    """Raised when authentication fails"""

    def __init__(
        self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class AuthorizationError(QuickRouteException):
    """Raised when user lacks permissions"""

    def __init__(
        self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN, details=details)


class NotFoundError(QuickRouteException):
    """Raised when resource is not found"""

    def __init__(
        self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ValidationError(QuickRouteException):
    """Raised when input validation fails"""

    def __init__(
        self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details
        )


class DatabaseError(QuickRouteException):
    """Raised when database operation fails"""

    def __init__(
        self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, details=details
        )


class TokenError(QuickRouteException):
    """Raised when token operations fail"""

    def __init__(self, message: str = "Token error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)
