"""
Veritabanı bağlantısı ve session yönetimi
SQLAlchemy async engine + connection pooling
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base

# Async engine — SQLite veya PostgreSQL
_url = settings.DATABASE_URL
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+asyncpg://")

_is_sqlite = _url.startswith("sqlite")

if _is_sqlite:
    engine = create_async_engine(
        _url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        _url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.DEBUG,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency Injection için veritabanı session'ı sağlar.
    Her request için yeni bir session açılır ve request bitince kapatılır.

    Kullanım:
        @router.get("/invoices")
        async def list_invoices(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Geliştirme ortamında tabloları oluştur (prod'da Alembic kullan)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
