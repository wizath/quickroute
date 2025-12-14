from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .settings import settings

# Async engine with debug echo from settings
engine = create_async_engine(settings.DATABASE_URL, future=True, echo=settings.DEBUG)

# Async session factory
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# Base class for models
class Base(DeclarativeBase):
    pass


async def get_async_session():
    """
    Dependency function to get async database session.

    Returns:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_session():
    """
    Get a database session (non-async version for testing).

    Returns:
        AsyncSessionLocal: Database session factory
    """
    return AsyncSessionLocal
