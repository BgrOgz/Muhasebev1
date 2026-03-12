"""
Alembic ortam konfigürasyonu — database migration yönetimi
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Tüm modelleri import et (migration'lar bunları görmek zorunda)
from app.models import Base  # noqa: F401
from app.config import settings

# Alembic Config nesnesi
config = context.config

# Logging konfigürasyonu
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata — hangi tabloların migrate edileceğini belirler
target_metadata = Base.metadata

# Database URL'i settings'den al
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
)


def run_migrations_offline() -> None:
    """Offline mod — sadece SQL script üretir, DB bağlantısı gerekmez"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Async engine ile migration çalıştır"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Online mod — gerçek DB bağlantısı ile migration"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
