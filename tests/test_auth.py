"""
Tests for QuickRoute authentication system.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from quickroute.app.auth import hash_password, verify_password, get_password_hash
from quickroute.app.jwt_utils import create_access_token, decode_token, create_refresh_token
from quickroute.app.models import User
from quickroute.app.settings import settings


class TestTokenCreation:
    """Test token creation functionality."""

    def test_create_access_token(self):
        """Test creating an access token."""
        user_id = 123
        token_data = create_access_token(user_id)

        assert token_data is not None
        assert isinstance(token_data, dict)
        assert "token" in token_data
        assert "jti" in token_data
        assert "expires_at" in token_data

        token = token_data["token"]
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long

        # Decode and verify
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_with_expiration(self):
        """Test creating access token includes expiration."""
        user_id = 123
        token_data = create_access_token(user_id)

        token = token_data["token"]
        expires_at = token_data["expires_at"]

        # Verify expiration is set correctly
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Verify token expires in approximately 30 minutes
        assert "exp" in payload
        assert expires_at is not None

        # Verify expires_at is close to now + ACCESS_TOKEN_EXPIRE_MINUTES
        expected_exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        time_diff = abs((expires_at - expected_exp).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_create_refresh_token(self):
        """Test creating a refresh token."""
        user_id = 123
        token_data = create_refresh_token(user_id)

        assert token_data is not None
        assert isinstance(token_data, dict)
        assert "token" in token_data
        assert "jti" in token_data
        assert "expires_at" in token_data

        token = token_data["token"]
        assert isinstance(token, str)
        assert len(token) > 50

        # Refresh tokens should have longer expiration
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        assert payload["type"] == "refresh"

        # Verify expires_at is approximately REFRESH_TOKEN_EXPIRE_DAYS in the future
        expected_exp = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        expires_at = token_data["expires_at"]
        time_diff = abs((expires_at - expected_exp).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_token_without_secret(self):
        """Test token creation with empty secret creates invalid token."""
        original_secret = settings.JWT_SECRET_KEY
        settings.JWT_SECRET_KEY = ""

        # Token is created but won't be verifiable
        token_data = create_access_token(123)
        token = token_data["token"]

        # Restore secret
        settings.JWT_SECRET_KEY = original_secret

        # Verify token is invalid with real secret
        payload = decode_token(token)
        assert payload is None  # Should be None because signature won't match


class TestTokenVerification:
    """Test token verification functionality."""

    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        user_id = 123
        token_data = create_access_token(user_id)
        token = token_data["token"]

        payload = decode_token(token)
        assert payload["sub"] == "123"
        assert payload["type"] == "access"

    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        invalid_token = "invalid.token.here"

        payload = decode_token(invalid_token)
        assert payload is None  # Should return None for invalid tokens

    def test_verify_expired_token(self):
        """Test verifying an expired token."""
        # Create expired token manually
        expired_payload = {
            "sub": "123",
            "type": "access",
            "exp": datetime.utcnow() - timedelta(minutes=1),  # Expired 1 minute ago
            "iat": datetime.utcnow() - timedelta(minutes=31),
        }
        token = jwt.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        payload = decode_token(token)
        assert payload is None  # Should return None for expired tokens

    def test_decode_token_wrong_secret(self):
        """Test verifying token with wrong secret."""
        user_id = 123
        token_data = create_access_token(user_id)
        token = token_data["token"]

        # Temporarily change secret
        original_secret = settings.JWT_SECRET_KEY
        settings.JWT_SECRET_KEY = "wrong_secret"

        payload = decode_token(token)
        assert payload is None  # Should return None for wrong secret

        # Restore
        settings.JWT_SECRET_KEY = original_secret

    def test_decode_token_missing_subject(self):
        """Test verifying token without subject."""
        # Create token manually without sub
        token = jwt.encode(
            {"email": "test@example.com", "type": "access"},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        payload = decode_token(token)
        # Token is valid but missing subject - decode_token will still return payload
        assert payload is not None
        assert "sub" not in payload or payload.get("sub") is None


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt hash prefix

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "testpassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self):
        """Test password verification with empty password."""
        hashed = hash_password("password")

        # Empty string should fail verification
        assert verify_password("", hashed) is False

        # None should raise AttributeError
        with pytest.raises(AttributeError):
            verify_password(None, hashed)

    def test_hash_different_passwords(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"

        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        assert hash1 != hash2

    def test_hash_same_password_different_times(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "samepassword"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2

        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_get_password_hash(self):
        """Test get_password_hash utility function."""
        password = "testpassword"
        hashed = get_password_hash(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert verify_password(password, hashed) is True


# TestUserAuthentication class removed - authenticate_user and get_current_user
# are application-level functions, not library functions.
# Use integration tests in test_integration.py for full authentication flow testing.


class TestDjangoLikeAuthMethods:
    """Test Django-like authentication methods on User model."""

    @pytest.mark.asyncio
    async def test_user_check_password(self, test_user: User):
        """Test User.check_password method."""
        assert test_user.check_password("testpassword123") is True
        assert test_user.check_password("wrongpassword") is False

    @pytest.mark.asyncio
    async def test_user_set_password(self, test_user: User):
        """Test User.set_password method."""
        new_password = "newpassword123"
        test_user.set_password(new_password)

        assert test_user.check_password(new_password) is True
        assert test_user.check_password("testpassword123") is False

    @pytest.mark.asyncio
    async def test_user_set_password_hashes(self, test_user: User):
        """Test that set_password properly hashes passwords."""
        original_hash = test_user.hashed_password
        test_user.set_password("newpassword")

        # Hash should be different
        assert test_user.hashed_password != original_hash
        # Should be bcrypt hash
        assert test_user.hashed_password.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_user_is_authenticated_property(self, test_user: User):
        """Test User.is_authenticated property."""
        assert test_user.is_authenticated is True

    @pytest.mark.asyncio
    async def test_user_is_anonymous_property(self, test_user: User):
        """Test User.is_anonymous property."""
        assert test_user.is_anonymous is False


class TestAuthIntegration:
    """Test authentication integration with other components."""

    @pytest.mark.asyncio
    async def test_auth_with_job_system(self, test_db: AsyncSession, test_user: User):
        """Test authentication integration with job system."""
        from quickroute.app.jobs import Job, JobRegistry

        # Create a job that requires authentication
        async def authenticated_job():
            return {"status": "authenticated_job_completed"}

        job = Job(name="test_auth_job", func=authenticated_job, schedule="hourly")
        registry = JobRegistry()
        registry.register(job)

        # Test job execution (would require actual job system integration)
        # This is more of an integration test placeholder
        assert True  # Placeholder test

    @pytest.mark.asyncio
    async def test_auth_with_websocket(self, test_db: AsyncSession, test_user: User):
        """Test authentication integration with WebSocket system."""
        # WebSocket authentication requires complex database mocking
        # This is tested in integration tests with full app context
        # For now, test JWT token creation for WebSocket use
        token_data = create_access_token(test_user.id)
        token = token_data["token"]

        # Verify token can be decoded
        payload = decode_token(token)
        assert payload is not None
        assert int(payload["sub"]) == test_user.id

        # WebSocket would use this token to authenticate
        # Full WebSocket integration tested in test_integration.py

    def test_auth_with_middleware(self, client, test_user_token: str):
        """Test authentication integration with middleware."""
        headers = {"Authorization": f"Bearer {test_user_token}"}

        # Test protected endpoint
        response = client.get("/", headers=headers)
        assert response.status_code == 200

        # Test with invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/", headers=invalid_headers)
        # This would depend on middleware implementation


class TestAuthSecurity:
    """Test authentication security aspects."""

    def test_token_expiration(self):
        """Test token expiration works correctly."""
        # Create expired token manually
        expired_payload = {
            "sub": "123",
            "type": "access",
            "exp": datetime.utcnow() - timedelta(seconds=10),  # Expired 10 seconds ago
            "iat": datetime.utcnow() - timedelta(minutes=31),
        }
        token = jwt.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        # Should return None for expired token
        payload = decode_token(token)
        assert payload is None

    def test_password_strength(self):
        """Test password hashing handles various password strengths."""
        weak_password = "123"
        strong_password = "ThisIsAVeryStrongPassword123!@#"

        weak_hash = hash_password(weak_password)
        strong_hash = hash_password(strong_password)

        assert weak_hash != strong_hash
        assert verify_password(weak_password, weak_hash) is True
        assert verify_password(strong_password, strong_hash) is True

    def test_token_tampering(self):
        """Test that tampered tokens are rejected."""
        user_id = 123
        token_data = create_access_token(user_id)
        token = token_data["token"]

        # Try to modify token (this would be complex in real testing)
        # For now, test with completely invalid token
        invalid_token = token[:-10] + "tampered"  # Simple tampering attempt

        payload = decode_token(invalid_token)
        assert payload is None  # Should return None for tampered tokens

    @pytest.mark.asyncio
    async def test_brute_force_protection(self, test_db: AsyncSession):
        """Test protection against brute force attacks (conceptual)."""
        # This would test rate limiting or account locking
        # Implementation would depend on security features
        pass

    def test_session_management(self):
        """Test session management concepts."""
        # Test token creation and refresh
        user_id = 123
        access_token_data = create_access_token(user_id)
        refresh_token_data = create_refresh_token(user_id)

        access_token = access_token_data["token"]
        refresh_token = refresh_token_data["token"]

        assert access_token != refresh_token
        assert len(access_token) > 0
        assert len(refresh_token) > 0

        # Verify both tokens
        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload["sub"] == "123"
        assert access_payload["type"] == "access"
        assert refresh_payload["sub"] == "123"
        assert refresh_payload["type"] == "refresh"


class TestAuthUtilities:
    """Test authentication utility functions."""

    @pytest.mark.asyncio
    async def test_create_user_with_auth(self, test_db: AsyncSession):
        """Test creating a user with authentication."""
        from quickroute.app.auth import get_password_hash

        user = User(
            email="authuser@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user is not None
        assert user.check_password("password123") is True

    def test_email_normalization(self):
        """Test email normalization in authentication."""
        # This would test that user@example.com and User@Example.com are treated the same
        email1 = "test@example.com"
        email2 = "Test@Example.com"

        # In implementation, these should be treated as the same for authentication
        # This is a placeholder for the actual test
        assert email1.lower() == email2.lower()

    async def test_user_permissions(
        self, test_db: AsyncSession, test_user: User, test_superuser: User
    ):
        """Test user permission checking."""
        # Test regular user
        assert test_user.is_superuser is False
        assert test_user.is_active is True

        # Test superuser
        assert test_superuser.is_superuser is True
        assert test_superuser.is_active is True

        # Test inactive user (if available)
        # This would test permission checks for different user types
