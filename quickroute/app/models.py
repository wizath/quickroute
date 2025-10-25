import asyncio
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from datetime import datetime
from .database import Base
from .managers import AsyncModelManager


class QuickRouteModel(Base):
    """
    base model class for QuickRoute.

    Provides common model functionality and methods.
    """

    __abstract__ = True

    objects = AsyncModelManager()

    def __str__(self):
        """Default string representation."""
        return f"{self.__class__.__name__}({self.id})"

    def __repr__(self):
        """Default repr representation."""
        return f"<{self.__class__.__name__}: {self.id}>"

class User(QuickRouteModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    objects = AsyncModelManager()

    def __str__(self):
        """string representation"""
        return self.email

    def __repr__(self):
        """repr"""
        return f"<User: {self.email}>"

    @property
    def is_authenticated(self):
        """Always True for authenticated users"""
        return True

    @property
    def is_anonymous(self):
        """Always False for authenticated users"""
        return False

    def set_password(self, raw_password: str):
        """Set password using method"""
        from .auth import hash_password
        self.hashed_password = hash_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check password using method"""
        from .auth import verify_password
        return verify_password(raw_password, self.hashed_password)

    def get_full_name(self) -> str:
        """method - returns email since we don't have name fields"""
        return self.email

    def get_short_name(self) -> str:
        """method - returns email"""
        return self.email

    def has_perm(self, perm: str) -> bool:
        """permission check - simplified"""
        return self.is_superuser

    def has_module_perms(self, app_label: str) -> bool:
        """module permission check - simplified"""
        return self.is_superuser

    def natural_key(self) -> tuple:
        """natural key"""
        return (self.email,)

    def save(self, session=None, update_fields=None):
        """
        save method - needs session parameter for async
        Note: This is a simplified version for demonstration
        """
        if session:
            asyncio.create_task(self._async_save(session, update_fields))

    async def _async_save(self, session: AsyncSession, update_fields=None):
        """Async save implementation"""
        session.add(self)
        await session.commit()
        await session.refresh(self)

    def delete(self, session=None):
        """
        delete method - needs session parameter for async
        """
        if session:
            asyncio.create_task(self._async_delete(session))

    async def _async_delete(self, session: AsyncSession):
        """Async delete implementation"""
        await session.delete(self)
        await session.commit()


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'access' or 'refresh'
    blacklisted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    objects = AsyncModelManager()

    def __str__(self):
        """string representation"""
        return f"BlacklistedToken: {self.jti[:8]}..."

    def __repr__(self):
        """repr"""
        return f"<BlacklistedToken: {self.jti[:8]}... ({self.token_type})>"

    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if token is still valid (not expired)"""
        return not self.is_expired()
