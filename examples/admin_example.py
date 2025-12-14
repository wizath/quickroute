#!/usr/bin/env python3
"""
QuickRoute Admin Example

This example demonstrates the SQLAdmin integration with JWT authentication.
Shows how to set up a Django-like admin panel for managing data.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, Text, DateTime
from datetime import datetime

# Import from QuickRoute library
from quickroute import QuickRoute, User, setup_admin, ADMIN_AVAILABLE
from quickroute.database import Base
from quickroute.settings import BaseSettings


# 1. Configure Settings
class Settings(BaseSettings):
    """Settings for admin example."""

    QUICKROUTE_TITLE = "QuickRoute Admin Demo"
    QUICKROUTE_DESCRIPTION = "Demonstrating SQLAdmin with JWT authentication"
    QUICKROUTE_VERSION = "1.0.0"

    DATABASE_URL = "sqlite+aiosqlite:///./admin_example.db"

    SECRET_KEY = "admin-demo-secret-key-change-in-production"
    JWT_SECRET_KEY = "admin-demo-jwt-secret-change-in-production"

    ENABLE_ADMIN = True
    ADMIN_TITLE = "QuickRoute Admin Demo"
    ADMIN_URL = "/admin"


# 2. Create Settings Instance
settings = Settings()


# 3. Define Models for Admin
class BlogPost(Base):
    """Blog post model for demonstration."""

    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(String(500))
    author_id: Mapped[int] = mapped_column(String(320), nullable=False)  # User email as FK
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __str__(self):
        return self.title


class Comment(Base):
    """Comment model for blog posts."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to BlogPost
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    author_email: Mapped[str] = mapped_column(String(320), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __str__(self):
        return f"Comment by {self.author_name} on post {self.post_id}"


class Category(Base):
    """Category model for blog posts."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#007bff")  # Hex color
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __str__(self):
        return self.name


# 4. Create QuickRoute App
app = QuickRoute(
    title="QuickRoute Admin Demo", description="Demonstrating SQLAdmin with JWT authentication"
)


# 5. Database Setup
engine = create_async_engine(settings.DATABASE_URL, echo=False)


# 6. Setup Admin Panel
if ADMIN_AVAILABLE:
    admin = setup_admin(app.get_app(), engine, use_jwt_auth=True)
    print("✅ Admin panel configured with JWT authentication")
else:
    print("❌ SQLAdmin not available. Install with: pip install sqladmin")


# 7. Demo Data Creation
async def create_demo_data():
    """Create demo data for the admin panel."""
    print("Creating demo data for admin...")

    from quickroute import UserManager

    # Create admin user
    user_manager = UserManager()

    try:
        admin_user = await user_manager.create_superuser(
            email="admin@example.com", password="admin123"
        )
        print(f"✅ Created admin user: {admin_user.email}")
    except:
        print("ℹ️  Admin user already exists")

    # Create demo categories
    categories_data = [
        {
            "name": "Technology",
            "description": "Posts about technology and programming",
            "color": "#007bff",
        },
        {"name": "Design", "description": "UI/UX design articles", "color": "#28a745"},
        {"name": "Business", "description": "Business and startup content", "color": "#ffc107"},
        {"name": "Tutorial", "description": "How-to guides and tutorials", "color": "#17a2b8"},
    ]

    for cat_data in categories_data:
        try:
            category = await Category.objects.create(**cat_data)
            print(f"✅ Created category: {category.name}")
        except:
            print(f"ℹ️  Category '{cat_data['name']}' already exists")

    # Create demo blog posts
    posts_data = [
        {
            "title": "Getting Started with QuickRoute",
            "slug": "getting-started-with-fastdjango",
            "content": "QuickRoute brings Django's simplicity to FastAPI. Learn how to build async web applications with Django-like patterns.",
            "excerpt": "A comprehensive guide to building async web apps with QuickRoute.",
            "author_id": "admin@example.com",
            "is_published": True,
            "is_featured": True,
        },
        {
            "title": "JWT Authentication Best Practices",
            "slug": "jwt-authentication-best-practices",
            "content": "Learn how to implement secure JWT authentication in your FastAPI applications. This guide covers token handling, security considerations, and common pitfalls.",
            "excerpt": "Security best practices for JWT authentication in modern web applications.",
            "author_id": "admin@example.com",
            "is_published": True,
            "is_featured": True,
        },
        {
            "title": "Building Admin Panels with SQLAdmin",
            "slug": "building-admin-panels-with-sqladmin",
            "content": "SQLAdmin provides Django-like admin interfaces for FastAPI applications. Learn how to set up admin panels, customize views, and manage permissions.",
            "excerpt": "Create beautiful admin interfaces for your FastAPI applications using SQLAdmin.",
            "author_id": "admin@example.com",
            "is_published": True,
            "is_featured": False,
        },
        {
            "title": "Async Database Operations with SQLAlchemy",
            "slug": "async-database-operations-sqlalchemy",
            "content": "Master async database operations with SQLAlchemy 2.0. This guide covers async sessions, queries, and best practices for high-performance applications.",
            "excerpt": "Learn how to perform efficient async database operations with SQLAlchemy 2.0.",
            "author_id": "admin@example.com",
            "is_published": False,
            "is_featured": False,
        },
    ]

    for post_data in posts_data:
        try:
            post = await BlogPost.objects.create(**post_data)
            print(f"✅ Created post: {post.title}")

            # Add some comments to published posts
            if post.is_published:
                comments_data = [
                    {
                        "post_id": post.id,
                        "author_name": "John Doe",
                        "author_email": "john@example.com",
                        "content": f"Great article about {post.title.lower()}!",
                        "is_approved": True,
                    },
                    {
                        "post_id": post.id,
                        "author_name": "Jane Smith",
                        "author_email": "jane@example.com",
                        "content": "Thanks for sharing this information. Very helpful!",
                        "is_approved": True,
                    },
                ]

                for comment_data in comments_data:
                    try:
                        await Comment.objects.create(**comment_data)
                        print(f"  ✅ Added comment to '{post.title}'")
                    except:
                        print(f"  ℹ️  Comment already exists for '{post.title}'")

        except:
            print(f"ℹ️  Post '{post_data['title']}' already exists")


# 8. API Routes (Optional)
from quickroute import Router

api_router = Router(prefix="/api", tags=["api"])


@api_router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "QuickRoute Admin Demo",
        "admin_url": settings.ADMIN_URL,
        "features": [
            "JWT Authentication",
            "SQLAdmin Integration",
            "Django-like Admin Panel",
            "User Management",
            "Blog Post Management",
            "Comment Moderation",
        ],
    }


@api_router.get("/stats")
async def get_stats():
    """Get basic statistics."""
    post_count = await BlogPost.objects.filter(is_published=True).count()
    comment_count = await Comment.objects.filter(is_approved=True).count()
    user_count = await User.objects.filter(is_active=True).count()

    return {
        "published_posts": post_count,
        "approved_comments": comment_count,
        "active_users": user_count,
    }


app.include_router(api_router)


# 9. Main Function
async def main():
    """Initialize database and show information."""
    # Create demo data
    await create_demo_data()

    print("\n🎛️  QuickRoute Admin Demo")
    print("=" * 40)
    print("📊 Admin Features:")
    print("  👥 User Management (Django-like permissions)")
    print("  📝 Blog Post Management")
    print("  💬 Comment Moderation")
    print("  🏷️  Category Management")
    print("  🔐 JWT Authentication Integration")
    print()
    print("🔑 Admin Credentials:")
    print("  Email: admin@example.com")
    print("  Password: admin123")
    print()
    print("🌐 Access Points:")
    print(f"  📋 Admin Panel: http://localhost:8000{settings.ADMIN_URL}")
    print("  📚 API Docs: http://localhost:8000/docs")
    print("  📊 API Root: http://localhost:8000/api")
    print()
    print("✨ Features:")
    print("  • Django-like admin interface")
    print("  • JWT-based authentication")
    print("  • Search and filtering")
    print("  • CRUD operations")
    print("  • Bulk actions")
    print("  • Export functionality")
    print()
    print("🚀 Starting server...")


if __name__ == "__main__":
    import uvicorn

    # Run initialization
    asyncio.run(main())

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
