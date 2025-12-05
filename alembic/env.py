from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import get_settings
from app.models.base import Base  # noqa: F401 ensure models import
import app.models  # noqa: F401

config = context.config
settings = get_settings()
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    cmd_opts = context.get_x_argument(as_dictionary=True)
    url = cmd_opts.get("url", settings.database_url)
    if url.startswith("postgresql:"):
        url = url.replace("postgresql:", "postgresql+asyncpg:", 1)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cmd_opts = context.get_x_argument(as_dictionary=True)
    sync_url = cmd_opts.get("url", settings.database_url)
    if sync_url.startswith("sqlite+aiosqlite"):
        sync_url = sync_url.replace("sqlite+aiosqlite", "sqlite", 1)
    if sync_url.startswith("postgresql+asyncpg"):
        sync_url = sync_url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)

    section = dict(config.get_section(config.config_ini_section) or {})
    section["sqlalchemy.url"] = sync_url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

