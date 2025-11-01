"""
Custom middleware examples for QuickRoute.
"""

import time
from .middleware import MiddlewareMixin, middleware
from fastapi import Request, Response
from .logging import logger


@middleware
class MaintenanceMiddleware(MiddlewareMixin):
    """
    Custom middleware for maintenance mode.
    """

    async def process_request(self, request: Request) -> Response:
        maintenance_mode = False  # Get from settings or database

        if maintenance_mode:
            # Allow admin users during maintenance
            if (
                hasattr(request.state, "user")
                and request.state.user
                and request.state.user.is_superuser
            ):
                return None

            return Response(
                content="<h1>Site Under Maintenance</h1><p>We'll be back soon!</p>",
                status_code=503,
                media_type="text/html",
            )

        return None


@middleware
class APIThrottlingMiddleware(MiddlewareMixin):
    """
    Simple API rate limiting middleware.
    In production, use Redis or external service for distributed throttling.
    """

    def __init__(self):
        self.request_counts = {}  # In production, use Redis

    async def process_request(self, request: Request) -> Response:
        client_ip = self._get_client_ip(request)
        current_time = int(time.time())

        # Clean old entries (older than 1 minute)
        self._cleanup_old_requests(current_time)

        if client_ip in self.request_counts:
            requests_this_minute = len(self.request_counts[client_ip])
            if requests_this_minute >= 100:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                    },
                )

        # Record this request
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        self.request_counts[client_ip].append(current_time)

        return None

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.client:
            return request.client.host

        return "unknown"

    def _cleanup_old_requests(self, current_time: int):
        """Remove requests older than 1 minute."""
        cutoff_time = current_time - 60

        for ip in list(self.request_counts.keys()):
            # Keep only requests within the last minute
            self.request_counts[ip] = [
                req_time for req_time in self.request_counts[ip] if req_time > cutoff_time
            ]

            if not self.request_counts[ip]:
                del self.request_counts[ip]


@middleware
class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Enhanced request logging middleware.
    """

    async def process_request(self, request: Request) -> None:
        request.state.start_time = time.time()

        # Log request details
        logger.info(
            f"📥 {request.method} {request.url.path} - "
            f"IP: {self._get_client_ip(request)} - "
            f"UA: {request.headers.get('user-agent', 'Unknown')[:50]}"
        )

    async def process_response(self, request: Request, response: Response) -> Response:
        # Calculate processing time
        if hasattr(request.state, "start_time"):
            processing_time = time.time() - request.state.start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

        # Log response details
        processing_time = response.headers.get("X-Processing-Time", "N/A")
        logger.info(
            f"📤 {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {processing_time}"
        )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.client:
            return request.client.host

        return "unknown"


@middleware
class CacheControlMiddleware(MiddlewareMixin):
    """
    Cache control middleware for static assets.
    """

    async def process_response(self, request: Request, response: Response) -> Response:
        if request.url.path.startswith("/static/") or request.url.path.startswith("/media/"):
            response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour
        elif request.url.path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg")):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 1 day
        else:
            # No caching for API responses
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


# Example of conditional middleware
class ConditionalMiddleware(MiddlewareMixin):
    """
    Middleware that only runs under certain conditions.
    """

    async def process_request(self, request: Request) -> None:
        # Only log requests from specific user agents
        user_agent = request.headers.get("user-agent", "")
        if "bot" in user_agent.lower() or "crawler" in user_agent.lower():
            logger.info(f"🤖 Bot detected: {user_agent}")

    async def process_response(self, request: Request, response: Response) -> Response:
        if request.url.path.startswith("/api/"):
            response.headers["X-API-Version"] = "1.0.0"
            response.headers["X-Powered-By"] = "QuickRoute"

        return response
