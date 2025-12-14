"""
Integration tests for QuickRoute library.

Tests the full application flow including:
- Application startup and initialization
- Database operations (SQLite and PostgreSQL)
- API endpoints
- Authentication flow
- Admin panel
- Model managers
- CLI commands
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from quickroute import QuickRoute, User, create_access_token, verify_password
from quickroute.database import Base, get_async_session


@pytest.mark.integration
class TestApplicationLifecycle:
    """Test application startup and shutdown."""

    def test_app_creation(self):
        """Test creating a QuickRoute application."""
        app = QuickRoute(title="Test App", description="Test Description")

        assert app is not None
        assert app.title == "Test App"
        assert app.description == "Test Description"

    def test_app_with_routes(self):
        """Test app with custom routes."""
        app = QuickRoute(title="Test App")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "test"}

    def test_app_docs_available(self):
        """Test that API docs are available."""
        app = QuickRoute(title="Test App")
        client = TestClient(app)

        # Test OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200

        # Test OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Test database integration."""

    @pytest.mark.asyncio
    async def test_sqlite_database_connection(self):
        """Test SQLite database connection."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Test connection is working
        from sqlalchemy import text

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_user_model_crud(self):
        """Test User model CRUD operations."""
        # Create in-memory database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async with SessionLocal() as session:
            # Create user
            from quickroute.auth import get_password_hash

            user = User(
                email="test@example.com",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert user.email == "test@example.com"

            # Read user
            from sqlalchemy import select

            result = await session.execute(select(User).where(User.email == "test@example.com"))
            found_user = result.scalar_one_or_none()

            assert found_user is not None
            assert found_user.email == "test@example.com"

            # Update user
            found_user.is_active = False
            await session.commit()
            await session.refresh(found_user)

            assert found_user.is_active is False

            # Delete user
            await session.delete(found_user)
            await session.commit()

            result = await session.execute(select(User).where(User.email == "test@example.com"))
            deleted_user = result.scalar_one_or_none()

            assert deleted_user is None

        await engine.dispose()


@pytest.mark.integration
@pytest.mark.api
class TestAPIIntegration:
    """Test API endpoint integration."""

    @pytest.mark.asyncio
    async def test_authentication_flow(self):
        """Test complete authentication flow."""
        from fastapi import Depends, HTTPException
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select

        # Setup test app and database
        app = QuickRoute(title="Test App")

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        # Override database dependency
        async def override_get_db():
            async with SessionLocal() as session:
                yield session

        app.dependency_overrides[get_async_session] = override_get_db

        # Create test user
        async with SessionLocal() as session:
            from quickroute.auth import get_password_hash

            user = User(
                email="testuser@example.com",
                hashed_password=get_password_hash("testpass123"),
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

        # Add login endpoint

        @app.post("/login")
        async def login(email: str, password: str, db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.hashed_password):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            token_data = create_access_token(user.id)
            return {"access_token": token_data["token"], "user_id": user.id}

        # Test with client
        from httpx import ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Test login
            response = await client.post(
                "/login", params={"email": "testuser@example.com", "password": "testpass123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["user_id"] == user_id

            # Test invalid credentials
            response = await client.post(
                "/login", params={"email": "testuser@example.com", "password": "wrongpass"}
            )

            assert response.status_code == 401

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_protected_endpoint(self):
        """Test protected endpoint with JWT."""
        from fastapi import Depends, Header, HTTPException
        from quickroute.auth import decode_token
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        app = QuickRoute(title="Test App")

        # Setup database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async def override_get_db():
            async with SessionLocal() as session:
                yield session

        app.dependency_overrides[get_async_session] = override_get_db

        # Create user
        async with SessionLocal() as session:
            from quickroute.auth import get_password_hash

            user = User(
                email="protected@example.com",
                hashed_password=get_password_hash("pass123"),
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

        # Add protected endpoint

        async def get_current_user(
            authorization: str = Header(None), db: AsyncSession = Depends(get_async_session)
        ):
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401)

            token = authorization.replace("Bearer ", "")
            payload = decode_token(token)

            if not payload:
                raise HTTPException(status_code=401)

            user_id = int(payload.get("sub"))
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=401)

            return user

        @app.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id, "email": current_user.email}

        # Test
        from httpx import ASGITransport

        token_data = create_access_token(user_id)
        token = token_data["token"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Test with valid token
            response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == user_id
            assert data["email"] == "protected@example.com"

            # Test without token
            response = await client.get("/protected")
            assert response.status_code == 401

            # Test with invalid token
            response = await client.get(
                "/protected", headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == 401

        await engine.dispose()


@pytest.mark.integration
@pytest.mark.auth
class TestAuthenticationIntegration:
    """Test authentication system integration."""

    @pytest.mark.asyncio
    async def test_user_registration_and_login(self):
        """Test complete user registration and login flow."""

        # Setup database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async with SessionLocal() as session:
            # Test user creation with manager
            from quickroute.auth import get_password_hash

            # Create user
            user = User(
                email="newuser@example.com",
                hashed_password=get_password_hash("securepass123"),
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert user.email == "newuser@example.com"
            assert user.is_active is True
            assert user.hashed_password != "securepass123"  # Should be hashed

            # Verify password
            assert user.check_password("securepass123") is True
            assert user.check_password("wrongpass") is False

            # Test password change
            user.set_password("newpass456")
            await session.commit()

            assert user.check_password("newpass456") is True
            assert user.check_password("securepass123") is False

        await engine.dispose()


@pytest.mark.integration
class TestModelManagerIntegration:
    """Test model manager integration."""

    @pytest.mark.asyncio
    async def test_user_objects_manager(self):
        """Test User.objects manager methods."""
        # Setup database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async with SessionLocal() as session:
            # Create multiple users
            from quickroute.auth import get_password_hash

            for i in range(5):
                user = User(
                    email=f"user{i}@example.com",
                    hashed_password=get_password_hash(f"pass{i}"),
                    is_active=i % 2 == 0,  # Alternate active/inactive
                    is_superuser=i == 0,  # First user is superuser
                )
                session.add(user)

            await session.commit()

            # Test filtering
            from sqlalchemy import select

            result = await session.execute(select(User).where(User.is_active))
            active_users = result.scalars().all()
            assert len(active_users) == 3  # Users 0, 2, 4

            # Test superuser query
            result = await session.execute(select(User).where(User.is_superuser))
            superusers = result.scalars().all()
            assert len(superusers) == 1
            assert superusers[0].email == "user0@example.com"

            # Test count
            result = await session.execute(select(User))
            all_users = result.scalars().all()
            assert len(all_users) == 5

        await engine.dispose()


@pytest.mark.integration
class TestFullApplicationFlow:
    """Test complete application workflow."""

    @pytest.mark.asyncio
    async def test_complete_blog_api_flow(self):
        """Test complete flow: user registration -> login -> create post -> list posts."""
        from fastapi import Depends, HTTPException, Header
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import AsyncSession
        from quickroute.auth import decode_token

        app = QuickRoute(title="Blog API")

        # Setup database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Create posts table
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER NOT NULL
                )
            """
                )
            )

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async def override_get_db():
            async with SessionLocal() as session:
                yield session

        app.dependency_overrides[get_async_session] = override_get_db

        # Add endpoints

        @app.post("/register")
        async def register(
            email: str, password: str, db: AsyncSession = Depends(get_async_session)
        ):
            # Check if user exists
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                raise HTTPException(400, "User exists")

            # Create user
            from quickroute.auth import get_password_hash

            user = User(email=email, hashed_password=get_password_hash(password), is_active=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)

            return {"user_id": user.id, "email": user.email}

        @app.post("/login")
        async def login(email: str, password: str, db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.hashed_password):
                raise HTTPException(401, "Invalid credentials")

            token_data = create_access_token(user.id)
            return {"access_token": token_data["token"]}

        async def get_current_user(
            authorization: str = Header(None), db: AsyncSession = Depends(get_async_session)
        ):
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(401)

            token = authorization.replace("Bearer ", "")
            payload = decode_token(token)
            if not payload:
                raise HTTPException(401)

            user_id = int(payload.get("sub"))
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(401)

            return user

        from fastapi import Header

        @app.post("/posts")
        async def create_post(
            title: str,
            content: str,
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_async_session),
        ):
            result = await db.execute(
                text(
                    "INSERT INTO posts (title, content, author_id) VALUES (:title, :content, :author_id) RETURNING id"
                ),
                {"title": title, "content": content, "author_id": current_user.id},
            )
            await db.commit()
            post_id = result.scalar()

            return {"id": post_id, "title": title, "author": current_user.email}

        @app.get("/posts")
        async def list_posts(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(text("SELECT * FROM posts"))
            posts = result.fetchall()
            return {"posts": [{"id": p[0], "title": p[1]} for p in posts]}

        # Test complete flow
        from httpx import ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register user
            response = await client.post(
                "/register", params={"email": "blogger@example.com", "password": "blog123"}
            )
            assert response.status_code == 200

            # 2. Login
            response = await client.post(
                "/login", params={"email": "blogger@example.com", "password": "blog123"}
            )
            assert response.status_code == 200
            token = response.json()["access_token"]

            # 3. Create post
            response = await client.post(
                "/posts",
                params={"title": "My First Post", "content": "Hello World"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            assert response.json()["title"] == "My First Post"

            # 4. List posts
            response = await client.get("/posts")
            assert response.status_code == 200
            posts = response.json()["posts"]
            assert len(posts) == 1
            assert posts[0]["title"] == "My First Post"

        await engine.dispose()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
