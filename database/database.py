"""إدارة اتصال قاعدة البيانات وتهيئة الجداول."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import get_settings
from database.models import Base

logger = logging.getLogger(__name__)


class Database:
    """غلاف بسيط حول SQLAlchemy async engine.

    مثال الاستخدام:
        async with db.session() as session:
            await session.execute(...)
    """

    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema ready.")

    async def close(self) -> None:
        await self.engine.dispose()


_db: Database | None = None


def init_db(url: str) -> Database:
    """إنشاء مثيل قاعدة البيانات مرة واحدة (Singleton)."""
    global _db
    if _db is None:
        _db = Database(url)
    return _db


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _db
