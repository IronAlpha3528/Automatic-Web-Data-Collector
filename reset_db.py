"""Drops all tables and enum types, then recreates them from the ORM models."""
import asyncio
from sqlalchemy import text
from project.config.database import engine, Base
import project.models.job
import project.models.url_record
import project.models.page
import project.models.media
import project.models.error_log


async def reset():
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS job_status_enum CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS url_status_enum CASCADE"))

    # Recreate all tables with updated schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("All tables dropped and recreated successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset())
