#!/usr/bin/env python3
"""
QuickRoute Basic App Example

This example demonstrates the core features of QuickRoute:
- Django-like model with manager
- JWT authentication
- Simple API routes
- User management
"""

import asyncio
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime
from datetime import datetime

# Import from QuickRoute library
from quickroute import (
    QuickRoute,
    User,
    create_access_token,
    decode_token,
    verify_password,
    get_password_hash,
    UserManager
)
from quickroute.app.database import Base
from quickroute.app.settings import BaseSettings


# 1. Configure Settings
class Settings(BaseSettings):
    """Example settings for the basic app."""

    # App info
    QUICKROUTE_TITLE = "QuickRoute Basic App"
    QUICKROUTE_DESCRIPTION = "A basic QuickRoute application"
    QUICKROUTE_VERSION = "1.0.0"

    # Database
    DATABASE_URL = "sqlite+aiosqlite:///./basic_app.db"

    # Security
    SECRET_KEY = "your-secret-key-change-in-production"
    JWT_SECRET_KEY = "your-jwt-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    # Admin
    ENABLE_ADMIN = True


# 2. Create Settings Instance
settings = Settings()


# 3. Define Additional Models
class Note(Base):
    """Simple note model to demonstrate custom models."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[int] = mapped_column(String(255), nullable=False)  # User email
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __str__(self):
        return self.title


# 4. Create QuickRoute App
app = QuickRoute(
    title="QuickRoute Basic App",
    description="A basic QuickRoute application example"
)


# 5. Define API Routes
from quickroute import Router

router = Router(prefix="/api", tags=["notes"])

@router.get("/notes")
async def list_notes():
    """List all public notes."""
    notes = await Note.objects.filter(is_public=True).all()
    return {"notes": notes}

@router.post("/notes")
async def create_note(title: str, content: str, is_public: bool = False):
    """Create a new note."""
    note = await Note.objects.create(
        title=title,
        content=content,
        is_public=is_public,
        author_id="demo@example.com"  # In real app, use current user
    )
    return {"note": note, "message": "Note created successfully"}

@router.get("/notes/{note_id}")
async def get_note(note_id: int):
    """Get a specific note."""
    note = await Note.objects.get(id=note_id)
    if not note or not note.is_public:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"note": note}


# 6. Authentication Routes
auth_router = Router(prefix="/auth", tags=["authentication"])

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    """Get current user from JWT token."""
    try:
        payload = decode_token(token.credentials)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = int(payload.get("sub"))
        user = await User.objects.get(id=user_id)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token")

@auth_router.post("/login")
async def login(email: str, password: str):
    """Login user and return JWT token."""
    # Find user (in real app, use proper authentication)
    user = await User.objects.filter(email=email).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is not active")

    # Create access token
    token_data = create_access_token(user.id)

    return {
        "access_token": token_data["token"],
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email}
    }

@auth_router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser
        }
    }


# 7. User Management Routes
user_router = Router(prefix="/users", tags=["users"])

@user_router.post("/register")
async def register_user(email: str, password: str):
    """Register a new user."""
    # Check if user already exists
    existing_user = await User.objects.filter(email=email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user
    user_manager = UserManager()
    user = await user_manager.create_user(
        email=email,
        password=password,
        is_active=True
    )

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active
        },
        "message": "User registered successfully"
    }


# 8. Include Routers
app.include_router(router)
app.include_router(auth_router)
app.include_router(user_router)


# 9. Utility Functions
async def create_demo_data():
    """Create some demo data for testing."""
    print("Creating demo data...")

    # Create demo user
    user_manager = UserManager()

    try:
        demo_user = await user_manager.create_user(
            email="demo@example.com",
            password="demo123",
            is_active=True,
            is_superuser=True
        )
        print(f"Created demo user: {demo_user.email}")
    except:
        print("Demo user already exists")

    # Create some demo notes
    notes_data = [
        {
            "title": "Welcome to QuickRoute",
            "content": "This is a basic example of QuickRoute with Django-like patterns.",
            "is_public": True
        },
        {
            "title": "JWT Authentication",
            "content": "QuickRoute includes built-in JWT authentication with secure cookies.",
            "is_public": True
        },
        {
            "title": "Admin Panel",
            "content": "SQLAdmin integration provides Django-like admin interface.",
            "is_public": True
        }
    ]

    for note_data in notes_data:
        try:
            note = await Note.objects.create(**note_data)
            print(f"Created note: {note.title}")
        except:
            print(f"Note '{note_data['title']}' already exists")


# 10. Main Function
async def main():
    """Initialize database and run the app."""
    # Create demo data
    await create_demo_data()

    print("\n🚀 QuickRoute Basic App")
    print("=" * 40)
    print("📊 Available endpoints:")
    print("  GET  /api/notes        - List public notes")
    print("  POST /api/notes       - Create a note")
    print("  POST /auth/login      - Login and get JWT token")
    print("  GET  /auth/me         - Get current user info")
    print("  POST /users/register  - Register a new user")
    print("  GET  /admin           - Admin panel (requires superuser)")
    print("\n🔑 Demo Credentials:")
    print("  Email: demo@example.com")
    print("  Password: demo123")
    print("\n🏃 Running on http://localhost:8000")
    print("📚 API docs: http://localhost:8000/docs")
    print("🎛️  Admin panel: http://localhost:8000/admin")


if __name__ == "__main__":
    import uvicorn

    # Run the initialization
    asyncio.run(main())

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)