import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Lazy engine initialization
_engine = None
_AsyncSessionLocal = None


def get_database_url():
    """Get database URL from environment."""
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./db.sqlite")


def get_engine():
    """Get or create async engine."""
    global _engine
    if _engine is None:
        debug = os.getenv("DEBUG", "False").lower() == "true"
        _engine = create_async_engine(get_database_url(), future=True, echo=debug)
    return _engine


def get_session_factory():
    """Get or create async session factory."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _AsyncSessionLocal


# Backwards compatible properties
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(get_engine(), name)

    def begin(self):
        return get_engine().begin()


class _SessionProxy:
    def __call__(self):
        return get_session_factory()()

    def __getattr__(self, name):
        return getattr(get_session_factory(), name)


engine = _EngineProxy()
AsyncSessionLocal = _SessionProxy()


# Base class for models
class Base(DeclarativeBase):
    pass


async def get_async_session():
    """
    Dependency function to get async database session.

    Returns:
        AsyncSession: Database session
    """
    async with get_session_factory()() as session:
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
    return get_session_factory()
