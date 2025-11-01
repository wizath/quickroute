"""
QuickRoute Admin Authentication.

Integrates SQLAdmin with JWT authentication system.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqladmin import Admin
from starlette.responses import Response
import jwt

from .settings import settings
from .jwt_utils import decode_token
from .models import User


class AdminAuth:
    """
    Admin authentication handler for QuickRoute.

    Integrates JWT token authentication with SQLAdmin.
    """

    def __init__(self, admin: Admin):
        self.admin = admin
        self.admin.login_manager = self.login_admin
        self.admin.logout_manager = self.logout_admin
        self.admin.auth_manager = self.authenticate_admin

    async def login_admin(self, request: Request) -> bool:
        """
        Handle admin login using JWT authentication.

        This method is called by SQLAdmin when accessing protected admin pages.
        """
        access_token = request.cookies.get("access_token")

        if not access_token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                access_token = auth_header.split(" ")[1]

        if not access_token:
            return False

        try:
            payload = decode_token(access_token)
            if not payload:
                return False

            user_id = int(payload.get("sub"))
            user = await User.objects.get(id=user_id)

            if not user or not user.is_active:
                return False

            if not user.is_superuser:
                return False

            request.state.user = user
            request.state.admin_user = user

            return True

        except (ValueError, KeyError, jwt.PyJWTError):
            return False

    async def logout_admin(self, request: Request) -> Response:
        """
        Handle admin logout.

        Clears JWT cookies and redirects to login page.
        """
        response = RedirectResponse(url="/admin/login", status_code=302)

        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        request.session.clear()

        return response

    async def authenticate_admin(self, request: Request) -> bool:
        """
        Check if current user has admin access.

        This is called for each admin request to verify permissions.
        """
        if hasattr(request.state, "admin_user") and request.state.admin_user:
            return True

        return await self.login_admin(request)


class QuickRouteAdmin(Admin):
    """
    QuickRoute Admin with JWT authentication integration.
    """

    def __init__(
        self,
        app,
        engine,
        authentication_url: str = "/admin/login",
        logout_url: str = "/admin/logout",
        title: str = "QuickRoute Admin",
    ):
        super().__init__(app, engine)

        self.authentication_url = authentication_url
        self.logout_url = logout_url
        self.title = title

        self.auth = AdminAuth(self)
        self._setup_auth_routes(app)

    def _setup_auth_routes(self, app):
        """Setup custom authentication routes."""

        @app.get("/admin/login")
        async def admin_login(request: Request):
            """Admin login page."""
            if await self.auth.authenticate_admin(request):
                return RedirectResponse(url="/admin", status_code=302)

            from fastapi.templating import Jinja2Templates

            templates = Jinja2Templates(directory="templates")
            return templates.TemplateResponse(
                "admin_login.html",
                {
                    "request": request,
                    "title": "Admin Login - QuickRoute",
                    "message": "Please login with your admin credentials",
                },
            )

        @app.post("/admin/login")
        async def admin_login_post(request: Request):
            """Handle admin login post request."""
            form = await request.form()
            email = form.get("email")
            password = form.get("password")

            if not email or not password:
                from fastapi.templating import Jinja2Templates

                templates = Jinja2Templates(directory="templates")
                return templates.TemplateResponse(
                    "admin_login.html",
                    {
                        "request": request,
                        "title": "Admin Login - QuickRoute",
                        "error": "Email and password are required",
                    },
                )

            from .dependencies import authenticate_user

            user = await authenticate_user(email, password)

            if not user or not user.is_active or not user.is_superuser:
                from fastapi.templating import Jinja2Templates

                templates = Jinja2Templates(directory="templates")
                return templates.TemplateResponse(
                    "admin_login.html",
                    {
                        "request": request,
                        "title": "Admin Login - QuickRoute",
                        "error": "Invalid credentials or insufficient permissions",
                    },
                )

            from .jwt_utils import create_access_token, create_refresh_token

            access_token_data = create_access_token(user.id)
            refresh_token_data = create_refresh_token(user.id)

            response = RedirectResponse(url="/admin", status_code=302)

            response.set_cookie(
                "access_token",
                access_token_data["token"],
                max_age=1800,  # 30 minutes
                httponly=True,
                secure=settings.DEBUG is False,
                samesite="lax",
            )

            response.set_cookie(
                "refresh_token",
                refresh_token_data["token"],
                max_age=30 * 24 * 60 * 60,  # 30 days
                httponly=True,
                secure=settings.DEBUG is False,
                samesite="lax",
            )

            return response

        @app.get("/admin/logout")
        async def admin_logout_route(request: Request):
            """Admin logout route."""
            return await self.auth.logout_admin(request)


def create_admin_with_auth(app, engine, **kwargs):
    """
    Create QuickRoute Admin with JWT authentication.

    Args:
        app: FastAPI application
        engine: SQLAlchemy engine
        **kwargs: Additional arguments for QuickRouteAdmin

    Returns:
        QuickRouteAdmin instance
    """
    return QuickRouteAdmin(app, engine, **kwargs)


# Middleware to handle JWT cookies for admin
class AdminJWTCookieMiddleware:
    """
    Middleware to handle JWT cookies for admin authentication.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from fastapi import Request

        request = Request(scope, receive)

        await self.app(scope, receive, send)
