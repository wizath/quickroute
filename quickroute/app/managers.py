from typing import Any, Dict, List, Optional, Type, TypeVar, TYPE_CHECKING
from contextlib import asynccontextmanager
from contextvars import ContextVar
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    pass

T = TypeVar("T", bound=DeclarativeBase)

# Context variable to hold the current transaction session
_current_session: ContextVar[Optional[AsyncSession]] = ContextVar("current_session", default=None)


class AsyncModelManager:
    """
    Model Manager for SQLAlchemy 2.0 async operations.

    Usage:
        # In model:
        class User(Base):
            # ... fields ...
            objects = AsyncModelManager()

        # In code:
        user = await User.objects.get(id=1)
        users = await User.objects.filter(is_active=True)
        all_users = await User.objects.all()
        new_user = await User.objects.create(email="test@example.com")
    """

    def __init__(self, model_class: Type[T] = None):
        self.model_class = model_class

    def __get__(self, instance, owner):
        """Allow use as class descriptor"""
        if self.model_class is None:
            self.model_class = owner
        return self

    def _get_session(self) -> AsyncSession:
        """Get database session - uses transaction session if available"""
        # Check if we're inside a transaction context
        session = _current_session.get()
        if session is not None:
            return session

        from .database import AsyncSessionLocal

        return AsyncSessionLocal()

    def _is_in_transaction(self) -> bool:
        """Check if we're inside a transaction context"""
        return _current_session.get() is not None

    @asynccontextmanager
    async def _session_scope(self):
        """
        Internal helper for session management.
        Uses transaction session if available, otherwise creates new session.
        """
        if self._is_in_transaction():
            yield self._get_session()
        else:
            async with self._get_session() as session:
                yield session

    @asynccontextmanager
    async def transaction(self):
        """
        Transaction context manager for grouping multiple operations.

        Usage:
            async with User.objects.transaction():
                user = await User.objects.create(email="test@example.com", ...)
                await Profile.objects.create(user_id=user.id, ...)
                # Both operations use the same session and transaction
                # Commits on success, rollbacks on exception
        """
        from .database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            token = _current_session.set(session)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                _current_session.reset(token)

    async def get(self, **kwargs) -> Optional[T]:
        """
        get() method.
        Returns single instance or None.

        Raises:
            sqlalchemy.orm.exc.MultipleResultsFound: if multiple results found
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model_class).filter_by(**kwargs))
            return result.scalar_one_or_none()

    async def filter(self, **kwargs) -> List[T]:
        """
        filter() method.
        Returns list of instances matching criteria.
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model_class).filter_by(**kwargs))
            return result.scalars().all()

    async def all(self) -> List[T]:
        """
        all() method.
        Returns all instances of the model.
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model_class))
            return result.scalars().all()

    async def create(self, **kwargs) -> T:
        """
        create() method.
        Creates and returns new instance.
        """
        async with self._session_scope() as session:
            instance = self.model_class(**kwargs)
            session.add(instance)
            if not self._is_in_transaction():
                await session.commit()
                await session.refresh(instance)
            return instance

    async def get_or_create(self, defaults: Dict[str, Any] = None, **kwargs) -> tuple[T, bool]:
        """
        get_or_create() method.
        Returns (instance, created) tuple.

        Args:
            defaults: Default values for creation if not found
            **kwargs: Fields to lookup and potentially create with
        """
        instance = await self.get(**kwargs)
        if instance:
            return instance, False

        create_data = defaults.copy() if defaults else {}
        create_data.update(kwargs)

        new_instance = await self.create(**create_data)
        return new_instance, True

    async def update_or_create(self, defaults: Dict[str, Any] = None, **kwargs) -> tuple[T, bool]:
        """
        update_or_create() method.
        Returns (instance, created) tuple.

        Args:
            defaults: Default values for creation/update
            **kwargs: Fields to lookup and potentially create/update with
        """
        async with self._session_scope() as session:
            instance = await self.get(**kwargs)

            if instance:
                update_data = defaults.copy() if defaults else {}
                for field, value in update_data.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)

                if not self._is_in_transaction():
                    await session.commit()
                    await session.refresh(instance)
                return instance, False
            else:
                create_data = defaults.copy() if defaults else {}
                create_data.update(kwargs)

                new_instance = self.model_class(**create_data)
                session.add(new_instance)
                if not self._is_in_transaction():
                    await session.commit()
                    await session.refresh(new_instance)
                return new_instance, True

    async def filter_exists(self, **kwargs) -> bool:
        """
        Check if any instance matching criteria exists.
        Returns True/False.
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model_class).filter_by(**kwargs).exists())
            return result.scalar()

    async def count(self, **kwargs) -> int:
        """
        count() method.
        Returns count of instances matching criteria.
        """
        async with self._session_scope() as session:
            if kwargs:
                result = await session.execute(select(self.model_class).filter_by(**kwargs))
                return len(result.scalars().all())
            else:
                from sqlalchemy import func

                result = await session.execute(select(func.count(self.model_class.id)))
                return result.scalar()

    async def delete(self, **kwargs) -> int:
        """
        delete() method.
        Deletes instances matching criteria and returns count.
        """
        async with self._session_scope() as session:
            result = await session.execute(delete(self.model_class).filter_by(**kwargs))
            if not self._is_in_transaction():
                await session.commit()
            return result.rowcount

    async def first(self) -> Optional[T]:
        """
        first() method.
        Returns first instance or None.
        """
        async with self._session_scope() as session:
            result = await session.execute(select(self.model_class).limit(1))
            return result.scalar_one_or_none()

    async def last(self) -> Optional[T]:
        """
        last() method.
        Returns last instance or None.
        """
        async with self._session_scope() as session:
            result = await session.execute(
                select(self.model_class).order_by(self.model_class.id.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    def __aiter__(self):
        """Allow async iteration over all instances"""
        return self._async_iter_all()

    async def _async_iter_all(self):
        """Async iterator implementation"""
        items = await self.all()
        for item in items:
            yield item


class AsyncQuerySet:
    """
    Advanced QuerySet for chaining operations.
    This allows method chaining like in Django:
        users = await User.objects.filter(is_active=True).order_by('email')
    """

    def __init__(
        self,
        model_class: Type[T],
        session: AsyncSession = None,
        filters: Dict[str, Any] = None,
        order_by: List[str] = None,
        limit: int = None,
        offset: int = None,
    ):
        self.model_class = model_class
        self._session = session
        self._filters = filters or {}
        self._order_by = order_by or []
        self._limit = limit
        self._offset = offset

    def filter(self, **kwargs) -> "AsyncQuerySet":
        """Add filter conditions"""
        new_filters = self._filters.copy()
        new_filters.update(kwargs)
        return AsyncQuerySet(
            self.model_class, self._session, new_filters, self._order_by, self._limit, self._offset
        )

    def order_by(self, *fields) -> "AsyncQuerySet":
        """Add ordering"""
        new_order = list(self._order_by) + list(fields)
        return AsyncQuerySet(
            self.model_class, self._session, self._filters, new_order, self._limit, self._offset
        )

    def limit(self, count: int) -> "AsyncQuerySet":
        """Set limit"""
        return AsyncQuerySet(
            self.model_class, self._session, self._filters, self._order_by, count, self._offset
        )

    def offset(self, count: int) -> "AsyncQuerySet":
        """Set offset"""
        return AsyncQuerySet(
            self.model_class, self._session, self._filters, self._order_by, self._limit, count
        )

    async def execute(self) -> List[T]:
        """Execute the query and return results"""
        from ..database import AsyncSessionLocal

        session = self._session or AsyncSessionLocal()

        try:
            query = select(self.model_class)

            # Apply filters
            if self._filters:
                query = query.filter_by(**self._filters)

            # Apply ordering
            for field in self._order_by:
                if field.startswith("-"):
                    # Descending order
                    query = query.order_by(getattr(self.model_class, field[1:]).desc())
                else:
                    # Ascending order
                    query = query.order_by(getattr(self.model_class, field))

            # Apply limit and offset
            if self._limit:
                query = query.limit(self._limit)
            if self._offset:
                query = query.offset(self._offset)

            result = await session.execute(query)
            return result.scalars().all()

        finally:
            if not self._session:
                await session.close()

    async def count(self) -> int:
        """Count results"""
        from ..database import AsyncSessionLocal
        from sqlalchemy import func

        session = self._session or AsyncSessionLocal()

        try:
            query = select(func.count(self.model_class.id))

            if self._filters:
                query = query.filter_by(**self._filters)

            result = await session.execute(query)
            return result.scalar()

        finally:
            if not self._session:
                await session.close()

    async def first(self) -> Optional[T]:
        """Get first result"""
        return (await self.limit(1).execute())[0] if await self.count() > 0 else None

    def __await__(self):
        """Allow direct awaiting: users = await User.objects.filter(is_active=True)"""
        return self.execute().__await__()


class UserManager(AsyncModelManager):
    """
    User-specific manager with user management methods.
    """

    async def create_user(self, email: str, password: str, **kwargs):
        """Create a user with hashed password."""
        from .auth.password import get_password_hash

        user = await self.create(email=email, hashed_password=get_password_hash(password), **kwargs)
        return user

    async def create_superuser(self, email: str, password: str, **kwargs):
        """Create a superuser."""
        return await self.create_user(
            email=email, password=password, is_superuser=True, is_active=True, **kwargs
        )

    async def get_by_email(self, email: str):
        """Get user by email."""
        return await self.get(email=email)


objects = AsyncModelManager()
