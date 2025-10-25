"""
Pytest configuration and fixtures for QuickRoute tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from quickroute.app.database import Base
from quickroute.app.main import app
from quickroute import User, create_access_token, UserManager
from quickroute.app.models import BlacklistedToken
from quickroute.app.settings import settings
from quickroute.app.database import get_async_session


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    testing_session_local = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override the dependency
    async def override_get_async_session():
        async with testing_session_local() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_async_session

    # Provide session to test
    async with testing_session_local() as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Remove override
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    from quickroute.app.auth import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_superuser(test_db: AsyncSession) -> User:
    """Create a test superuser."""
    from quickroute.app.auth import get_password_hash

    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        is_superuser=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user: User) -> str:
    """Create a JWT token for test user."""
    token_data = create_access_token(test_user.id)
    return token_data["token"]


@pytest.fixture
def test_superuser_token(test_superuser: User) -> str:
    """Create a JWT token for test superuser."""
    token_data = create_access_token(test_superuser.id)
    return token_data["token"]


@pytest.fixture
def auth_headers(test_user_token: str) -> dict:
    """Authentication headers for test user."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture
def superuser_headers(test_superuser_token: str) -> dict:
    """Authentication headers for test superuser."""
    return {"Authorization": f"Bearer {test_superuser_token}"}


@pytest.fixture
async def multiple_users(test_db: AsyncSession) -> list[User]:
    """Create multiple test users."""
    from quickroute.app.auth import get_password_hash
    users = []

    for i in range(5):
        user = User(
            email=f"user{i+1}@example.com",
            hashed_password=get_password_hash(f"password{i+1}"),
            is_active=True,
            is_superuser=False
        )
        test_db.add(user)
        users.append(user)

    await test_db.commit()
    for user in users:
        await test_db.refresh(user)

    return users


@pytest.fixture
async def inactive_user(test_db: AsyncSession) -> User:
    """Create an inactive test user."""
    from quickroute.app.auth import get_password_hash

    user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=False,
        is_superuser=False
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


# WebSocket test fixtures
@pytest.fixture
async def websocket_test_client():
    """Create a WebSocket test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# Job system test fixtures
@pytest.fixture
def mock_celery():
    """Mock Celery for testing."""
    import pytest
    from unittest.mock import Mock, patch

    with patch('app.celery.app.celery_app') as mock_app:
        mock_app.task = lambda name=None, bind=False, **kwargs: lambda func: func
        mock_app.conf = Mock()
        mock_app.conf.broker_url = "memory://"
        mock_app.conf.result_backend = "memory://"
        mock_app.autodiscover_tasks = Mock()
        yield mock_app


# Plugin system test fixtures
@pytest.fixture
def test_plugin():
    """Create a test plugin."""
    from quickroute.app.plugins.base import BasePlugin
    from quickroute.app.settings import BaseSettings

    class TestPlugin(BasePlugin):
        @property
        def name(self) -> str:
            return "test_plugin"

        @property
        def description(self) -> str:
            return "Test plugin for unit testing"

        @property
        def version(self) -> str:
            return "1.0.0"

        def is_available(self) -> bool:
            return True

        def initialize(self) -> bool:
            self.test_data = {"initialized": True}
            return True

        def shutdown(self):
            self.test_data = {}

    return TestPlugin(BaseSettings())


# Settings test fixtures
@pytest.fixture
def test_settings():
    """Create test settings."""
    from quickroute.app.settings import TestingSettings
    return TestingSettings()


# Utility functions for tests
@pytest.fixture
def create_user_factory(test_db: AsyncSession):
    """Factory function to create users."""
    async def _create_user(email: str = None, password: str = None, **kwargs):
        from quickroute.app.auth import get_password_hash

        user = User(
            email=email or "test@example.com",
            hashed_password=get_password_hash(password or "testpassword123"),
            **kwargs
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)
        return user
    return _create_user


# Token blacklisting fixtures
@pytest.fixture
async def blacklisted_token(test_db: AsyncSession) -> BlacklistedToken:
    """Create a blacklisted token."""
    from datetime import datetime, timedelta

    blacklisted = BlacklistedToken(
        jti="test-jti-12345",
        token_type="access",
        blacklisted_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )
    test_db.add(blacklisted)
    await test_db.commit()
    await test_db.refresh(blacklisted)
    return blacklisted


@pytest.fixture
async def expired_blacklisted_token(test_db: AsyncSession) -> BlacklistedToken:
    """Create an expired blacklisted token."""
    from datetime import datetime, timedelta

    expired = BlacklistedToken(
        jti="expired-jti-67890",
        token_type="access",
        blacklisted_at=datetime.utcnow() - timedelta(days=2),
        expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
    )
    test_db.add(expired)
    await test_db.commit()
    await test_db.refresh(expired)
    return expired