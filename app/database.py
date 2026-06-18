from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def create_engine() -> AsyncEngine:
    settings = get_settings()

    return create_async_engine(settings.database_url, pool_pre_ping=True)


engine = create_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def check_database_ready() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text('SELECT 1'))
    except Exception:
        return False

    return True
