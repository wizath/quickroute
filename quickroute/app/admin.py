from sqladmin import Admin, ModelView
from fastapi import FastAPI, Request

from .models import User, BlacklistedToken
from .admin_auth import create_admin_with_auth
from .settings import settings


class UserAdmin(ModelView, model=User):
    """User admin interface with permissions."""

    column_list = [
        User.id,
        User.email,
        User.is_active,
        User.is_superuser,
        User.created_at,
        User.updated_at,
    ]

    column_searchable_list = [User.email]
    column_sortable_list = [User.created_at, User.updated_at]
    column_default_sort = [(User.created_at, True)]

    form_columns = [User.email, User.is_active, User.is_superuser]

    form_widget_args = {
        User.email: {"placeholder": "Enter email address", "type": "email"},
        User.is_active: {
            "disabled": False,
        },
        User.is_superuser: {
            "disabled": False,
        },
    }

    name = "User"
    name_plural = "Users"
    icon = "fas fa-users"

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True

    async def is_accessible(self, request: Request) -> bool:
        """Check if user has access to User admin."""
        if not hasattr(request.state, "admin_user"):
            return False

        admin_user = request.state.admin_user
        return admin_user and admin_user.is_superuser

    async def can_edit(self, request: Request) -> bool:
        """Check if user can edit."""
        return await self.is_accessible(request)

    async def can_delete(self, request: Request) -> bool:
        """Check if user can delete."""
        return await self.is_accessible(request)

    async def can_create(self, request: Request) -> bool:
        """Check if user can create."""
        return await self.is_accessible(request)


class BlacklistedTokenAdmin(ModelView, model=BlacklistedToken):
    """Blacklisted Token admin interface."""

    column_list = [
        BlacklistedToken.id,
        BlacklistedToken.jti,
        BlacklistedToken.token_type,
        BlacklistedToken.blacklisted_at,
        BlacklistedToken.expires_at,
    ]

    column_searchable_list = [BlacklistedToken.jti]
    column_sortable_list = [BlacklistedToken.blacklisted_at, BlacklistedToken.expires_at]
    column_default_sort = [(BlacklistedToken.blacklisted_at, True)]

    form_columns = []

    name = "Blacklisted Token"
    name_plural = "Blacklisted Tokens"
    icon = "fas fa-ban"

    can_create = False  # No manual creation
    can_edit = False  # No editing
    can_delete = True  # Allow manual deletion of expired tokens

    async def is_accessible(self, request: Request) -> bool:
        """Check if user has access to Token admin."""
        if not hasattr(request.state, "admin_user"):
            return False

        admin_user = request.state.admin_user
        return admin_user and admin_user.is_superuser

    async def can_delete(self, request: Request) -> bool:
        """Check if user can delete tokens."""
        return await self.is_accessible(request)


def setup_admin(app: FastAPI, engine, use_jwt_auth: bool = True):
    """
    Setup QuickRoute admin panel with optional JWT authentication.

    Args:
        app: FastAPI application
        engine: SQLAlchemy engine
        use_jwt_auth: Whether to use JWT authentication (default: True)

    Returns:
        Admin instance
    """
    if use_jwt_auth:
        admin = create_admin_with_auth(
            app=app, engine=engine, title=f"{settings.QUICKROUTE_TITLE} Admin"
        )
    else:
        admin = Admin(app=app, engine=engine, title=f"{settings.QUICKROUTE_TITLE} Admin")

    admin.add_view(UserAdmin)
    admin.add_view(BlacklistedTokenAdmin)

    return admin


def is_admin_enabled() -> bool:
    """
    Check if admin panel should be enabled based on settings.

    Returns:
        bool: True if admin should be enabled
    """
    return getattr(settings, "ENABLE_ADMIN", True)


try:
    from sqladmin import Admin

    ADMIN_AVAILABLE = True
except ImportError:
    ADMIN_AVAILABLE = False
