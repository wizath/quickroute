"""
Test framework base classes for QuickRoute.

Provides base test cases and utilities for testing QuickRoute applications.
"""

import pytest
import asyncio
from typing import Dict
from unittest.mock import Mock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from quickroute.main import app
from quickroute import User, create_access_token
from quickroute.settings import TestingSettings


class QuickRouteTestCase:
    """
    Base test case class for QuickRoute synchronous tests.

    Provides common utilities and setup for testing QuickRoute components.
    """

    def setup_method(self):
        """Set up test method."""
        self.client = TestClient(app)
        self.settings = TestingSettings()

    def create_user(
        self, email: str = "test@example.com", password: str = "test123", **kwargs
    ) -> User:
        """Create a test user synchronously for simple tests."""
        # This is a simplified version for sync tests
        user = Mock(spec=User)
        user.id = 1
        user.email = email
        user.hashed_password = "$2b$12$...hashed..."  # Mock hash
        user.is_active = kwargs.get("is_active", True)
        user.is_superuser = kwargs.get("is_superuser", False)
        return user

    def get_auth_headers(self, user: User) -> Dict[str, str]:
        """Get authentication headers for a user."""
        token = create_access_token(data={"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    def assert_response(self, response, status_code: int = 200, contains: str = None):
        """Assert response status and optional content."""
        assert response.status_code == status_code
        if contains:
            assert contains in response.json() or contains in response.text

    def assert_json_response(self, response, status_code: int = 200, data: Dict = None):
        """Assert JSON response with optional data validation."""
        assert response.status_code == status_code
        assert response.headers["content-type"] == "application/json"
        if data:
            response_data = response.json()
            for key, value in data.items():
                assert response_data[key] == value


class AsyncQuickRouteTestCase:
    """
    Base test case class for QuickRoute asynchronous tests.

    Provides async utilities and setup for testing QuickRoute components.
    """

    @pytest.fixture(autouse=True)
    async def setup_async_test(self, test_db: AsyncSession):
        """Set up async test with database."""
        self.db = test_db
        self.client = TestClient(app)
        self.settings = TestingSettings()

    async def create_user(
        self, email: str = "test@example.com", password: str = "test123", **kwargs
    ) -> User:
        """Create a test user in the database."""
        from quickroute.managers import UserManager

        user_manager = UserManager()
        return await user_manager.create(db=self.db, email=email, password=password, **kwargs)

    def get_auth_headers(self, user: User) -> Dict[str, str]:
        """Get authentication headers for a user."""
        token = create_access_token(data={"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    async def assert_json_response(self, response, status_code: int = 200, data: Dict = None):
        """Assert JSON response with optional data validation."""
        assert response.status_code == status_code
        if response.headers.get("content-type") == "application/json":
            response_data = response.json()
            if data:
                for key, value in data.items():
                    assert response_data[key] == value

    async def create_multiple_users(self, count: int = 3) -> list[User]:
        """Create multiple test users."""
        from quickroute.managers import UserManager

        user_manager = UserManager()
        users = []

        for i in range(count):
            user = await user_manager.create(
                db=self.db,
                email=f"user{i+1}@example.com",
                password=f"password{i+1}",
                is_active=True,
                is_superuser=False,
            )
            users.append(user)

        return users


class WebSocketTestCase(AsyncQuickRouteTestCase):
    """
    Base test case for WebSocket functionality.
    """

    async def create_websocket_connection(self, user: User = None, token: str = None):
        """Create a mock WebSocket connection for testing."""
        from quickroute.websocket.connection import WebSocketConnection
        from unittest.mock import Mock

        mock_websocket = Mock()
        mock_websocket.client = Mock()
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.headers = {"user-agent": "test-client"}
        mock_websocket.query_params = {}

        connection = WebSocketConnection(mock_websocket)

        if user:
            connection.user = user
            connection.authenticated = True

        if token:
            connection.add_metadata("token", token)

        return connection

    async def create_mock_room(self, name: str = "test_room"):
        """Create a mock WebSocket room for testing."""
        from quickroute.websocket.connection import WebSocketRoom

        return WebSocketRoom(name)


class JobTestCase(AsyncQuickRouteTestCase):
    """
    Base test case for job/periodic task functionality.
    """

    @pytest.fixture(autouse=True)
    def setup_job_test(self, mock_celery):
        """Set up job test with mocked Celery."""
        self.mock_celery = mock_celery

    async def create_test_job(self, name: str = "test_job"):
        """Create a test job for testing."""
        from quickroute.jobs import Job, JobRegistry

        async def test_job_func():
            return {"status": "completed", "job_name": name}

        job = Job(name=name, func=test_job_func, schedule="hourly")

        registry = JobRegistry()
        registry.register(job)

        return job

    async def run_job_test(self, job):
        """Run a job and return the result."""
        from quickroute.jobs import JobScheduler

        scheduler = JobScheduler()
        return await scheduler.run_job_now(job.name)


class PluginTestCase(AsyncQuickRouteTestCase):
    """
    Base test case for plugin functionality.
    """

    def create_test_plugin(self, name: str = "test_plugin"):
        """Create a test plugin."""
        from quickroute.plugins.base import BasePlugin
        from quickroute.settings import TestingSettings

        class TestPlugin(BasePlugin):
            def __init__(self, settings):
                super().__init__(settings)
                self.test_name = name

            @property
            def name(self) -> str:
                return self.test_name

            @property
            def description(self) -> str:
                return f"Test plugin: {self.test_name}"

            @property
            def version(self) -> str:
                return "1.0.0"

            def is_available(self) -> bool:
                return True

            def initialize(self) -> bool:
                self.initialized = True
                return True

            def shutdown(self):
                self.initialized = False

        return TestPlugin(TestingSettings())


class MiddlewareTestCase(AsyncQuickRouteTestCase):
    """
    Base test case for middleware functionality.
    """

    async def create_mock_request(self, method: str = "GET", path: str = "/", headers: Dict = None):
        """Create a mock request for middleware testing."""
        from fastapi import Request
        from unittest.mock import Mock

        mock_request = Mock(spec=Request)
        mock_request.method = method
        mock_request.url = Mock()
        mock_request.url.path = path
        mock_request.headers = headers or {}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"

        return mock_request

    async def call_middleware(self, middleware_class, request, *args, **kwargs):
        """Call middleware with a mock request."""
        middleware = middleware_class()

        async def mock_call_next(request):
            return {"status": "success"}

        return await middleware.process_request(request, mock_call_next)


class IntegrationTestCase(AsyncQuickRouteTestCase):
    """
    Base test case for integration tests.
    """

    async def setup_full_app(self):
        """Set up full application for integration testing."""
        # This would set up all components

        # Initialize plugins (might be mocked)
        # Initialize WebSocket middleware
        # Setup all routes

        pass

    async def test_full_request_cycle(
        self, method: str, path: str, headers: Dict = None, data: Dict = None
    ):
        """Test a full request cycle through the application."""
        if method.upper() == "GET":
            response = self.client.get(path, headers=headers or {})
        elif method.upper() == "POST":
            response = self.client.post(path, json=data, headers=headers or {})
        elif method.upper() == "PUT":
            response = self.client.put(path, json=data, headers=headers or {})
        elif method.upper() == "DELETE":
            response = self.client.delete(path, headers=headers or {})
        else:
            raise ValueError(f"Unsupported method: {method}")

        return response


# Utility functions for testing
async def create_test_app():
    """Create a test FastAPI application."""
    from quickroute.main import app

    return app


async def create_test_user(db: AsyncSession, email: str = "test@example.com", **kwargs) -> User:
    """Create a test user."""
    from quickroute.managers import UserManager

    user_manager = UserManager()
    return await user_manager.create(db=db, email=email, **kwargs)


def get_test_token(user_id: int) -> str:
    """Get a JWT test token."""
    return create_access_token(data={"sub": str(user_id)})


def assert_dict_subset(subset: Dict, full_dict: Dict):
    """Assert that subset dict is contained in full dict."""
    for key, value in subset.items():
        assert key in full_dict
        assert full_dict[key] == value


async def wait_for_async(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for an async condition to become true."""
    import time

    start_time = time.time()

    while time.time() - start_time < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)

    raise TimeoutError(f"Condition not met within {timeout} seconds")
