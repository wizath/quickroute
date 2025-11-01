"""
middleware system for QuickRoute.

Provides familiar middleware patterns for request/response processing.
"""

import time
import uuid
from typing import Callable, Dict, List, Optional, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .logging import logger
from .settings import settings


class MiddlewareMixin:
    """
    Base mixin class for creating middleware.

    Middleware pattern with process_request and process_response methods.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        """
        Called before the view function.
        Return Response to short-circuit the request.
        Return None to continue processing.
        """
        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        """
        Called after the view function.
        Must return a Response object.
        """
        return response

    async def process_exception(self, request: Request, exc: Exception) -> Optional[Response]:
        """
        Called when an exception occurs.
        Return Response to handle the exception.
        Return None to let other middleware handle it.
        """
        return None


class QuickRouteMiddleware(BaseHTTPMiddleware):
    """
    Base middleware class that integrates middleware with FastAPI.
    """

    def __init__(self, app, middleware_class):
        super().__init__(app)
        self.middleware_class = middleware_class()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await self.middleware_class.process_request(request)
        if response:
            return response

        try:
            response = await call_next(request)
        except Exception as exc:
            exception_response = await self.middleware_class.process_exception(request, exc)
            if exception_response:
                return exception_response
            raise

        response = await self.middleware_class.process_response(request, response)
        return response


class RequestIDMiddleware(MiddlewareMixin):
    """
    Adds unique request ID to each request for tracing.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        if hasattr(request.state, "request_id"):
            response.headers["X-Request-ID"] = request.state.request_id
        return response


class TimingMiddleware(MiddlewareMixin):
    """
    Measures request processing time.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        request.state.start_time = time.time()
        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        if hasattr(request.state, "start_time"):
            processing_time = time.time() - request.state.start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"
            logger.info(f"Request {request.method} {request.url.path} - {processing_time:.3f}s")
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds security headers to responses.
    """

    async def process_response(self, request: Request, response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class LoggingMiddleware(MiddlewareMixin):
    """
    Enhanced request/response logging.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        request.state.log_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
        }

        logger.info(f"Request started: {request.method} {request.url.path}")
        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        if hasattr(request.state, "log_data"):
            log_data = request.state.log_data
            log_data["status_code"] = response.status_code

            logger.info(
                f"Request completed: {log_data['method']} {log_data['path']} "
                f"- {response.status_code} - Client: {log_data['client_ip']}"
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to client IP
        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"


class SessionMiddleware(MiddlewareMixin):
    """
    Simple session middleware for QuickRoute.
    Uses memory storage for development (in production, use Redis or database).
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def process_request(self, request: Request) -> Optional[Response]:
        session_id = request.cookies.get("sessionid")

        if not session_id:
            session_id = str(uuid.uuid4())
            request.state.session = {}
            request.state.session_id = session_id
            request.state.session_modified = True
        else:
            request.state.session = self.sessions.get(session_id, {})
            request.state.session_id = session_id
            request.state.session_modified = False

        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        if hasattr(request.state, "session_modified") and request.state.session_modified:
            # Save session
            self.sessions[request.state.session_id] = request.state.session

            response.set_cookie(
                key="sessionid",
                value=request.state.session_id,
                max_age=settings.SESSION_COOKIE_AGE,
                httponly=settings.SESSION_COOKIE_HTTPONLY,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

        return response


class CSRFMiddleware(MiddlewareMixin):
    """
    CSRF protection middleware.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        # Skip CSRF for safe methods
        if request.method in ["GET", "HEAD", "OPTIONS", "TRACE"]:
            return None

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            csrf_token = request.headers.get("X-CSRFToken")
            session_token = getattr(request.state, "session", {}).get("csrf_token")

            if not csrf_token or not session_token or csrf_token != session_token:
                return JSONResponse(
                    status_code=403, content={"error": "CSRF token missing or invalid"}
                )

        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        if request.method in ["GET", "HEAD"]:
            if not hasattr(request.state, "session"):
                request.state.session = {}

            if "csrf_token" not in request.state.session:
                import secrets

                request.state.session["csrf_token"] = secrets.token_urlsafe(32)
                request.state.session_modified = True

            response.headers["X-CSRFToken"] = request.state.session["csrf_token"]

        return response


class UserMiddleware(MiddlewareMixin):
    """
    Automatically sets current user from session or token.
    """

    async def process_request(self, request: Request) -> Optional[Response]:
        if hasattr(request.state, "session"):
            user_id = request.state.session.get("user_id")
            if user_id:
                from .models import User
                from .database import AsyncSessionLocal
                from sqlalchemy import select

                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user and user.is_active:
                        request.state.user = user
                        request.state.authenticated = True
                        return None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from .jwt_utils import decode_token

            payload = decode_token(token)
            if payload:
                from .models import User
                from .database import AsyncSessionLocal
                from sqlalchemy import select

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(User).where(User.id == int(payload.get("sub")))
                    )
                    user = result.scalar_one_or_none()
                    if user and user.is_active:
                        request.state.user = user
                        request.state.authenticated = True

        if not hasattr(request.state, "user"):
            request.state.user = None
            request.state.authenticated = False

        return None


# Middleware factory functions
def create_request_id_middleware(app):
    """Create request ID middleware."""
    return QuickRouteMiddleware(app, RequestIDMiddleware)


def create_timing_middleware(app):
    """Create timing middleware."""
    return QuickRouteMiddleware(app, TimingMiddleware)


def create_security_headers_middleware(app):
    """Create security headers middleware."""
    return QuickRouteMiddleware(app, SecurityHeadersMiddleware)


def create_logging_middleware(app):
    """Create logging middleware."""
    return QuickRouteMiddleware(app, LoggingMiddleware)


def create_session_middleware(app):
    """Create session middleware."""
    return QuickRouteMiddleware(app, SessionMiddleware)


def create_csrf_middleware(app):
    """Create CSRF middleware."""
    return QuickRouteMiddleware(app, CSRFMiddleware)


def create_user_middleware(app):
    """Create user middleware."""
    return QuickRouteMiddleware(app, UserMiddleware)


# Built-in middleware that uses Starlette middleware
def add_cors_middleware(app):
    """Add CORS middleware using Starlette's CORSMiddleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def add_trusted_host_middleware(app):
    """Add trusted host middleware for security."""
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


def add_https_redirect_middleware(app):
    """Add HTTPS redirect middleware for production."""
    if not settings.DEBUG:
        app.add_middleware(HTTPSRedirectMiddleware)


# Middleware loader function
def load_middleware(app, middleware_classes: Optional[List[str]] = None):
    """
    Load middleware based on settings or provided list.

    Args:
        app: FastAPI application
        middleware_classes: List of middleware class names to load
                           If None, uses settings.MIDDLEWARE
    """
    if middleware_classes is None:
        middleware_classes = settings.MIDDLEWARE

    # Map middleware class names to factory functions
    middleware_map = {
        "app.middleware.RequestIDMiddleware": create_request_id_middleware,
        "app.middleware.TimingMiddleware": create_timing_middleware,
        "app.middleware.SecurityHeadersMiddleware": create_security_headers_middleware,
        "app.middleware.LoggingMiddleware": create_logging_middleware,
        "app.middleware.SessionMiddleware": create_session_middleware,
        "app.middleware.CSRFMiddleware": create_csrf_middleware,
        "app.middleware.UserMiddleware": create_user_middleware,
    }

    for middleware_path in middleware_classes:
        if middleware_path in middleware_map:
            middleware_map[middleware_path](app)
            logger.info(f"Loaded middleware: {middleware_path}")
        elif middleware_path == "starlette.middleware.cors.CORSMiddleware":
            add_cors_middleware(app)
        elif middleware_path == "starlette.middleware.trustedhost.TrustedHostMiddleware":
            add_trusted_host_middleware(app)
        elif middleware_path == "starlette.middleware.httpsredirect.HTTPSRedirectMiddleware":
            add_https_redirect_middleware(app)
        else:
            logger.warning(f"Unknown middleware: {middleware_path}")


# Decorator for middleware
def middleware(cls):
    """
    Decorator to mark a class as middleware.

    Usage:
        @middleware
        class CustomMiddleware(MiddlewareMixin):
            async def process_request(self, request):
                # Middleware logic here
                pass
    """
    cls._is_middleware = True
    return cls
