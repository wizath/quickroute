#!/usr/bin/env python3
"""
QuickRoute Testing Example

Shows how to use the QuickRoute test framework.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import QuickRoute
from quickroute import QuickRoute, QuickRouteTestCase
from quickroute.models import User


# Create a simple test app
app = QuickRoute(title="Test Example")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id, "name": f"User {user_id}"}


# Example unit tests
class TestAPI:
    """Test API endpoints."""

    def test_root_endpoint(self):
        """Test the root endpoint."""
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello World"}

    def test_get_user_endpoint(self):
        """Test the get user endpoint."""
        with TestClient(app) as client:
            response = client.get("/users/123")
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 123
            assert data["name"] == "User 123"


# Example database tests
class TestUserModel(QuickRouteTestCase):
    """Test User model."""

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test creating a user."""
        user = await self.create_user(
            email="test@example.com", password="testpass123", is_active=True
        )

        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_user_authentication(self):
        """Test user authentication."""
        from quickroute.auth import verify_password

        user = await self.create_user(email="auth@example.com", password="testpass123")

        # Test password verification
        assert verify_password("testpass123", user.hashed_password)
        assert not verify_password("wrongpass", user.hashed_password)

    @pytest.mark.asyncio
    async def test_user_model_methods(self):
        """Test Django-like model methods."""
        user = await self.create_user(email="methods@example.com", password="testpass123")

        # Test string representation
        assert str(user) == "methods@example.com"

        # Test password methods
        assert user.check_password("testpass123")
        assert not user.check_password("wrongpass")

        # Test set_password
        user.set_password("newpass123")
        assert user.check_password("newpass123")
        assert not user.check_password("testpass123")


# Example authentication tests
@pytest.mark.auth
class TestAuthentication(QuickRouteTestCase):
    """Test authentication system."""

    @pytest.mark.asyncio
    async def test_create_access_token(self):
        """Test JWT token creation."""
        from quickroute.auth import create_access_token, decode_token

        user = await self.create_user(email="token@example.com", password="testpass123")

        # Create token
        token_data = create_access_token(user.id)
        token = token_data["token"]

        assert token is not None
        assert len(token) > 0

        # Decode token
        payload = decode_token(token)
        assert payload is not None
        assert int(payload["sub"]) == user.id

    @pytest.mark.asyncio
    async def test_user_permissions(self):
        """Test user permissions."""
        # Create regular user
        user = await self.create_user(
            email="user@example.com", password="testpass123", is_superuser=False
        )

        assert user.is_superuser is False
        assert user.is_active is True

        # Create superuser
        admin = await self.create_user(
            email="admin@example.com", password="adminpass123", is_superuser=True
        )

        assert admin.is_superuser is True
        assert admin.is_active is True


# Example integration tests
@pytest.mark.integration
class TestIntegration(QuickRouteTestCase):
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_user_creation_and_authentication_flow(self):
        """Test complete user flow."""
        from quickroute.auth import create_access_token, decode_token

        # Create user
        user = await self.create_user(email="flow@example.com", password="testpass123")

        # Verify user exists in database
        await self.assertModelExists(User, email="flow@example.com")

        # Create authentication token
        token_data = create_access_token(user.id)
        token = token_data["token"]

        # Verify token is valid
        payload = decode_token(token)
        assert int(payload["sub"]) == user.id

        # Test user model methods
        assert user.check_password("testpass123")
        assert str(user) == "flow@example.com"


# Example async API tests
@pytest.mark.api
class TestAsyncAPI:
    """Test async API endpoints."""

    @pytest.mark.asyncio
    async def test_async_client(self):
        """Test with async client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello World"}

    @pytest.mark.asyncio
    async def test_async_user_endpoint(self):
        """Test async user endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/users/456")
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 456


# Performance test
@pytest.mark.slow
class TestPerformance(QuickRouteTestCase):
    """Performance tests."""

    @pytest.mark.asyncio
    async def test_bulk_user_creation(self):
        """Test creating many users efficiently."""
        import time

        start_time = time.time()

        # Create 100 users
        users = []
        for i in range(100):
            user = await self.create_user(email=f"user{i}@example.com", password=f"pass{i}")
            users.append(user)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time
        assert duration < 5.0  # 5 seconds
        assert len(users) == 100

        # Verify all users exist
        for i, user in enumerate(users):
            await self.assertModelExists(User, email=f"user{i}@example.com")


if __name__ == "__main__":
    # Run the tests
    import subprocess
    import sys

    print("Running QuickRoute test example...")
    print("Usage:")
    print("  quickroute test examples/test_example.py")
    print("  quickroute test examples/test_example.py -v")
    print("  quickroute test examples/test_example.py --tag auth")
    print("  quickroute test examples/test_example.py --tag integration")
    print()
    print("Running with quickroute test command...")

    # Run the tests
    result = subprocess.run([sys.executable, "-m", "fastdjango.cli", "test", __file__, "-v"])

    sys.exit(result.returncode)
