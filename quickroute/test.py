"""
QuickRoute Test Framework

Provides testing utilities and configuration.
"""

import os
import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Optional
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Test configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class QuickRouteTestClient:
    """Test client for QuickRoute applications."""

    def __init__(self, app, test_db_url: str = TEST_DATABASE_URL):
        from fastapi.testclient import TestClient
        from httpx import AsyncClient

        self.app = app
        self.test_db_url = test_db_url
        self._sync_client = TestClient(app)
        self._async_client = None

    @property
    def sync(self):
        """Synchronous test client."""
        return self._sync_client

    async def async_client(self) -> AsyncGenerator:
        """Async test client."""
        from httpx import AsyncClient
        async with AsyncClient(app=self.app, base_url="http://test") as client:
            yield client


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
    )

    from quickroute.app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine):
    """Create a test database session."""
    from sqlalchemy.orm import sessionmaker

    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def test_client(test_db_session):
    """Create a test client with database session."""
    from quickroute.app.database import get_async_session

    # Override the database dependency
    async def override_get_db():
        yield test_db_session

    try:
        from app.main import app
        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()
    except ImportError:
        # For library testing, create a minimal app
        from quickroute import QuickRoute
        app = QuickRoute(title="Test App")
        app.dependency_overrides[get_async_session] = override_get_db
        yield app
        app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_db_session):
    """Create a test user."""
    from quickroute.app.models import User
    from quickroute.app.auth import get_password_hash

    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_superuser=False
    )

    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)

    return user


@pytest.fixture
async def test_superuser(test_db_session):
    """Create a test superuser."""
    from quickroute.app.models import User
    from quickroute.app.auth import get_password_hash

    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpass123"),
        is_active=True,
        is_superuser=True
    )

    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)

    return user


@pytest.fixture
async def access_token(test_user):
    """Create a JWT access token for test user."""
    from quickroute.app.jwt_utils import create_access_token

    token_data = create_access_token(test_user.id)
    return token_data["token"]


@pytest.fixture
async def superuser_token(test_superuser):
    """Create a JWT access token for test superuser."""
    from quickroute.app.jwt_utils import create_access_token

    token_data = create_access_token(test_superuser.id)
    return token_data["token"]


class QuickRouteTestCase:
    """Base test case class for QuickRoute tests."""

    @pytest.fixture(autouse=True)
    async def setup_test_case(self, test_db_session):
        """Setup test case with database session."""
        self.db = test_db_session

    async def create_user(self, email: str, password: str, **kwargs):
        """Create a test user."""
        from quickroute.app.models import User
        from quickroute.app.auth import get_password_hash

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            **kwargs
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def assertModelExists(self, model_class, **filters):
        """Assert that a model instance exists."""
        from sqlalchemy import select

        result = await self.db.execute(select(model_class).filter_by(**filters))
        instance = result.scalar_one_or_none()

        assert instance is not None, f"{model_class.__name__} not found with filters: {filters}"
        return instance

    async def assertModelNotExists(self, model_class, **filters):
        """Assert that a model instance does not exist."""
        from sqlalchemy import select

        result = await self.db.execute(select(model_class).filter_by(**filters))
        instance = result.scalar_one_or_none()

        assert instance is None, f"{model_class.__name__} found with filters: {filters}"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with QuickRoute settings."""
    os.environ["QUICKROUTE_TESTING"] = "1"

    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "auth: Authentication tests"
    )
    config.addinivalue_line(
        "markers", "database: Database tests"
    )
    config.addinivalue_line(
        "markers", "api: API tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        if "auth" in item.name.lower():
            item.add_marker(pytest.mark.auth)
        if "database" in item.name.lower():
            item.add_marker(pytest.mark.database)
        if "api" in item.name.lower():
            item.add_marker(pytest.mark.api)