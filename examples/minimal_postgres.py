#!/usr/bin/env python3
"""
QuickRoute Minimal PostgreSQL Example

Single-file production-ready app with PostgreSQL support.

Quick Deploy:
    1. pip install quickroute[postgres]
    2. export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
    3. export SECRET_KEY=your-secret-key
    4. python minimal_postgres.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (falls back to SQLite)
    SECRET_KEY: Secret key for JWT tokens
    PORT: Server port (default: 8000)
"""

import os
from quickroute import QuickRoute

# Configure database (PostgreSQL in production, SQLite for dev)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./app.db"  # Local development fallback
)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
PORT = int(os.getenv("PORT", "8000"))

# Create app
app = QuickRoute(
    title="Minimal App",
    description="Production-ready minimal QuickRoute app"
)

# Override settings
from quickroute.app.settings import settings
settings.DATABASE_URL = DATABASE_URL
settings.SECRET_KEY = SECRET_KEY
settings.JWT_SECRET_KEY = SECRET_KEY

# Import models
from quickroute import User
from quickroute.app.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean
from datetime import datetime


# Define your models
class Post(Base):
    """Blog post model."""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[int] = mapped_column()


# API Routes
@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "database": DATABASE_URL.split("://")[0]}


@app.get("/posts")
async def list_posts():
    """List all published posts."""
    posts = await Post.objects.filter(published=True).all()
    return {"posts": [{"id": p.id, "title": p.title} for p in posts]}


@app.post("/posts")
async def create_post(title: str, content: str):
    """Create a new post."""
    post = await Post.objects.create(
        title=title,
        content=content,
        published=True,
        author_id=1
    )
    return {"id": post.id, "title": post.title}


# Authentication
from quickroute import create_access_token, verify_password
from fastapi import HTTPException


@app.post("/auth/register")
async def register(email: str, password: str):
    """Register new user."""
    existing = await User.objects.filter(email=email).first()
    if existing:
        raise HTTPException(400, "User exists")

    user = await User.objects.create(
        email=email,
        hashed_password=verify_password.__self__.hash(password),
        is_active=True
    )

    token_data = create_access_token(user.id)
    return {"token": token_data["token"], "user_id": user.id}


@app.post("/auth/login")
async def login(email: str, password: str):
    """Login user."""
    user = await User.objects.filter(email=email).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    token_data = create_access_token(user.id)
    return {"token": token_data["token"], "user_id": user.id}


# Startup
@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    from quickroute.app.database import engine

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"🚀 App started")
    print(f"📊 Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'SQLite'}")
    print(f"🔗 API: http://localhost:{PORT}")
    print(f"📚 Docs: http://localhost:{PORT}/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)