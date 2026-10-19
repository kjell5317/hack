from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def _set_search_path(conn) -> None:
    await conn.execute("set search_path to public, extensions")


@event.listens_for(engine.sync_engine, "connect")
def _on_connect(dbapi_connection, _record) -> None:
    # Supabase installs extensions into the `extensions` schema, and pgvector's
    # operators (<=>, ...) must be on the search_path. This runs on the raw
    # asyncpg connection so the SET isn't undone by a transaction rollback.
    # Don't also call pgvector.asyncpg.register_vector: pgvector.sqlalchemy's
    # Vector type already serialises to text and the binary codec rejects that.
    dbapi_connection.run_async(_set_search_path)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
