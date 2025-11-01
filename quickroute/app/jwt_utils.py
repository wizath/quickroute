import jwt
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
from .settings import settings


def create_access_token(user_id: int) -> dict:
    """Create JWT access token (30 minutes)"""
    jti = str(uuid4())
    expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "access",
        "exp": expires,
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"token": token, "jti": jti, "expires_at": expires}


def create_refresh_token(user_id: int) -> dict:
    """Create JWT refresh token (30 days)"""
    jti = str(uuid4())
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "refresh",
        "exp": expires,
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"token": token, "jti": jti, "expires_at": expires}


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_token_type(payload: dict, expected_type: str) -> bool:
    """Verify token type (access or refresh)"""
    return payload.get("type") == expected_type
