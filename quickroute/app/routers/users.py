from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from ..dependencies import get_session, get_current_user, get_current_superuser
from ..models import User

router = APIRouter()


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_superuser: bool

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_superuser),
):
    """List all users (superuser only)"""
    result = await session.scalars(select(User))
    return result.all()
