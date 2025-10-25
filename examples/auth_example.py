#!/usr/bin/env python3
"""
QuickRoute Authentication Example

This example demonstrates the complete JWT authentication system.
Shows user registration, login, protected routes, and token management.
"""

import asyncio
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta

# Import from QuickRoute library
from quickroute import (
    QuickRoute,
    User,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    get_password_hash,
    UserManager
)
from quickroute.app.database import Base, engine
from quickroute.app.settings import BaseSettings
from quickroute.app.models import BlacklistedToken


# 1. Configure Settings
class Settings(BaseSettings):
    """Settings for authentication example."""

    QUICKROUTE_TITLE = "QuickRoute Auth Demo"
    QUICKROUTE_DESCRIPTION = "Demonstrating JWT authentication system"
    QUICKROUTE_VERSION = "1.0.0"

    DATABASE_URL = "sqlite+aiosqlite:///./auth_example.db"

    SECRET_KEY = "auth-demo-secret-key-change-in-production"
    JWT_SECRET_KEY = "auth-demo-jwt-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 30

    ENABLE_ADMIN = True


# 2. Create Settings Instance
settings = Settings()


# 3. Define Additional Models
class UserProfile(Base):
    """Extended user profile model."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    bio: Mapped[str] = mapped_column(nullable=True)
    avatar_url: Mapped[str] = mapped_column(nullable=True)
    phone: Mapped[str] = mapped_column(nullable=True)
    date_of_birth: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    def __str__(self):
        return f"Profile for User ID: {self.user_id}"


# 4. Create QuickRoute App
app = QuickRoute(
    title="QuickRoute Auth Demo",
    description="Demonstrating JWT authentication system"
)


# 5. Authentication Dependencies
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token."""
    try:
        payload = decode_token(credentials.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = int(payload.get("sub"))
        user = await User.objects.get(id=user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_superuser(current_user: User = Depends(get_current_user)):
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# 6. Authentication Routes
from quickroute import Router

auth_router = Router(prefix="/auth", tags=["authentication"])


@auth_router.post("/register")
async def register(
    email: str,
    password: str,
    first_name: str = None,
    last_name: str = None
):
    """Register a new user."""
    # Check if user already exists
    existing_user = await User.objects.filter(email=email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate password
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )

    # Create user
    user_manager = UserManager()
    user = await user_manager.create_user(
        email=email,
        password=password,
        is_active=True
    )

    return {
        "message": "User registered successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active
        }
    }


@auth_router.post("/login")
async def login(email: str, password: str):
    """Login user and return JWT tokens."""
    # Authenticate user
    user = await User.objects.filter(email=email).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    # Create tokens
    access_token_data = create_access_token(user.id)
    refresh_token_data = create_refresh_token(user.id)

    return {
        "access_token": access_token_data["token"],
        "refresh_token": refresh_token_data["token"],
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }
    }


@auth_router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    # Decode refresh token
    payload = decode_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check if token is blacklisted
    blacklisted = await BlacklistedToken.objects.filter(jti=payload.get("jti")).first()
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )

    # Get user
    user_id = int(payload.get("sub"))
    user = await User.objects.get(id=user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Create new access token
    access_token_data = create_access_token(user.id)

    return {
        "access_token": access_token_data["token"],
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@auth_router.post("/logout")
async def logout(refresh_token: str, current_user: User = Depends(get_current_user)):
    """Logout user and blacklist tokens."""
    # Blacklist refresh token
    payload = decode_token(refresh_token)
    if payload:
        await BlacklistedToken.objects.create(
            jti=payload.get("jti"),
            token_type="refresh",
            expires_at=datetime.fromtimestamp(payload.get("exp"))
        )

    return {"message": "Successfully logged out"}


@auth_router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at
        }
    }


@auth_router.put("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user)
):
    """Change user password."""
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )

    # Update password
    current_user.set_password(new_password)
    # In a real implementation, you'd save the changes

    return {"message": "Password changed successfully"}


# 7. Protected Routes
protected_router = Router(prefix="/protected", tags=["protected"])


@protected_router.get("/profile")
async def get_protected_profile(current_user: User = Depends(get_current_user)):
    """Protected endpoint that requires authentication."""
    return {
        "message": "This is a protected endpoint",
        "user": {
            "id": current_user.id,
            "email": current_user.email
        }
    }


@protected_router.get("/admin")
async def admin_only_endpoint(current_user: User = Depends(get_current_superuser)):
    """Admin-only endpoint."""
    return {
        "message": "This is an admin-only endpoint",
        "admin": {
            "id": current_user.id,
            "email": current_user.email
        }
    }


# 8. Public Routes
public_router = Router(prefix="/public", tags=["public"])


@public_router.get("/")
async def public_root():
    """Public endpoint."""
    return {
        "message": "This is a public endpoint",
        "features": [
            "JWT Authentication",
            "User Registration",
            "Token Refresh",
            "Protected Routes",
            "Admin Access Control"
        ]
    }


@public_router.get("/info")
async def public_info():
    """Public information about the API."""
    return {
        "title": "QuickRoute Authentication Demo",
        "version": "1.0.0",
        "authentication": "JWT Bearer Token",
        "endpoints": {
            "public": "/public/*",
            "auth": "/auth/*",
            "protected": "/protected/* (requires authentication)"
        }
    }


# 9. Include Routers
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(protected_router)


# 10. Demo Data Creation
async def create_demo_users():
    """Create demo users for testing."""
    print("Creating demo users...")

    user_manager = UserManager()

    demo_users = [
        {
            "email": "user@example.com",
            "password": "user123",
            "is_superuser": False
        },
        {
            "email": "admin@example.com",
            "password": "admin123",
            "is_superuser": True
        }
    ]

    for user_data in demo_users:
        try:
            user = await user_manager.create_user(**user_data)
            role = "Admin" if user.is_superuser else "User"
            print(f"✅ Created {role}: {user.email} (password: {user_data['password']})")
        except:
            print(f"ℹ️  User {user_data['email']} already exists")


# 11. Main Function
async def main():
    """Initialize database and show authentication info."""
    # Create demo users
    await create_demo_users()

    print("\n🔐 QuickRoute Authentication Demo")
    print("=" * 45)
    print("📋 Authentication Features:")
    print("  ✅ User registration")
    print("  ✅ JWT login with access/refresh tokens")
    print("  ✅ Token refresh mechanism")
    print("  ✅ Password change")
    print("  ✅ Token blacklisting")
    print("  ✅ Protected routes")
    print("  ✅ Superuser-only access")
    print()
    print("🔑 Demo Credentials:")
    print("  Regular User: user@example.com / user123")
    print("  Admin User:  admin@example.com / admin123")
    print()
    print("📚 API Documentation:")
    print("  📖 Swagger UI: http://localhost:8000/docs")
    print("  🔒 ReDoc: http://localhost:8000/redoc")
    print()
    print("📊 Available Endpoints:")
    print("  🌐 Public: /public/*")
    print("  🔐 Auth: /auth/*")
    print("  🛡️ Protected: /protected/* (requires token)")
    print()
    print("🚀 Starting server...")


if __name__ == "__main__":
    import uvicorn

    # Run the demo
    asyncio.run(main())

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)