from __future__ import annotations

from functools import lru_cache

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.configs import get_database_settings

# Consistent constraint/index names so Alembic autogenerate produces stable,
# diffable migrations instead of driver-generated names that change per run.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Process-wide singleton engine — one connection pool for the app's lifetime.

    Repository calls are frequent and each opens its own session, so a fresh
    engine (and pool) per call would defeat the point of pooling entirely.
    """
    settings = get_database_settings()
    return create_async_engine(
        settings.database_url, echo=settings.DATABASE_ECHO, connect_args=settings.connect_args,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
