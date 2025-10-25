from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import AsyncSessionLocal
from .jwt_utils import decode_token, verify_token_type
from .models import User, BlacklistedToken
from .exceptions import AuthenticationError, AuthorizationError
from .logging import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Get current user from JWT token"""
    logger.debug(f"Authenticating user with token")

    # Decode token
    payload = decode_token(token)
    if not payload:
        logger.warning("Invalid or expired token provided")
        raise AuthenticationError("Could not validate credentials")

    if not verify_token_type(payload, "access"):
        logger.warning(f"Invalid token type provided: {payload.get('type')}")
        raise AuthenticationError("Invalid token type")

    jti = payload.get("jti")
    result = await session.execute(
        select(BlacklistedToken).where(BlacklistedToken.jti == jti)
    )
    if result.scalar_one_or_none():
        logger.warning(f"Attempted to use blacklisted token: {jti}")
        raise AuthenticationError("Token has been revoked")

    user_id = int(payload.get("sub"))
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"User not found for ID: {user_id}")
        raise AuthenticationError("User not found")

    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user.email}")
        raise AuthorizationError("User account is inactive")

    logger.debug(f"Successfully authenticated user: {user.email}")
    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify they are a superuser"""
    if not current_user.is_superuser:
        logger.warning(f"Non-superuser attempted admin access: {current_user.email}")
        raise AuthorizationError("Not enough permissions")

    logger.debug(f"Superuser access granted: {current_user.email}")
    return current_user
