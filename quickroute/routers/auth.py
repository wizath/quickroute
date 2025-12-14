from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from ..dependencies import get_session
from ..models import User, BlacklistedToken
from ..auth.password import verify_password
from ..auth.jwt import create_access_token, create_refresh_token, decode_token, verify_token_type
from ..exceptions import AuthenticationError, TokenError
from quickroute.logging import logger

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)
):
    """Login endpoint - returns access and refresh tokens"""
    logger.info(f"Login attempt for: {form_data.username}")

    # Find user by email (username field in OAuth2)
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise AuthenticationError("Incorrect email or password")

    if not user.is_active:
        logger.warning(f"Inactive user attempted login: {user.email}")
        raise AuthenticationError("User account is inactive")

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    logger.info(f"Successful login for: {user.email}")
    return TokenResponse(access_token=access["token"], refresh_token=refresh["token"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """Refresh access token using refresh token"""
    logger.debug("Token refresh attempt")

    payload = decode_token(request.refresh_token)

    if not payload:
        logger.warning("Invalid or expired refresh token provided")
        raise TokenError("Invalid or expired refresh token")

    if not verify_token_type(payload, "refresh"):
        logger.warning(f"Invalid token type for refresh: {payload.get('type')}")
        raise TokenError("Invalid token type")

    jti = payload.get("jti")
    result = await session.execute(select(BlacklistedToken).where(BlacklistedToken.jti == jti))
    if result.scalar_one_or_none():
        logger.warning(f"Attempted to refresh blacklisted token: {jti}")
        raise TokenError("Token has been revoked")

    user_id = int(payload.get("sub"))
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        logger.warning(f"Token refresh failed for user ID: {user_id}")
        raise AuthenticationError("User not found or inactive")

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    logger.debug(f"Token refreshed successfully for user: {user.email}")
    return TokenResponse(access_token=access["token"], refresh_token=refresh["token"])


@router.post("/logout")
async def logout(request: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """Logout - blacklist the refresh token"""
    logger.debug("Logout attempt")

    payload = decode_token(request.refresh_token)

    if not payload:
        logger.warning("Invalid token provided for logout")
        raise TokenError("Invalid token")

    # Blacklist the token
    from datetime import datetime

    jti = payload.get("jti")
    blacklisted = BlacklistedToken(
        jti=jti,
        token_type=payload.get("type", "refresh"),
        expires_at=datetime.fromtimestamp(payload.get("exp")),
    )
    session.add(blacklisted)

    try:
        await session.commit()
        logger.info(f"Token blacklisted successfully: {jti}")
    except Exception as e:
        logger.error(f"Failed to blacklist token: {e}")
        await session.rollback()
        raise

    return {"message": "Successfully logged out"}
