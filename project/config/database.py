"""
Asynchronous database setup using SQLAlchemy 2.0 and asyncpg.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from project.config.settings import settings

# Initialize async engine with connection pooling and asyncpg driver
engine: AsyncEngine = create_async_engine(
    settings.get_async_database_url(),
    echo=(settings.app_env == "development"),
    pool_pre_ping=True,
    future=True,
)

# Thread-safe async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Declarative Base for ORM entities
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to provide an isolated async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Creates all defined database tables asynchronously."""
    # Ensure all models are loaded in Base.metadata
    import project.models.job
    import project.models.url_record
    import project.models.page
    import project.models.media
    import project.models.error_log

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
