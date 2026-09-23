import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importing app.models registers every ORM model (and therefore every table)
# on Base.metadata, so autogenerate and the target schema see the full model
# set for this service.
import app.models  # noqa: F401
from app.database import Base

# Alembic Config object, providing access to values in alembic.ini.
config = context.config

# Configure Python logging from the config file, if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    """Build a SYNC SQLAlchemy URL for Alembic.

    The application talks to Postgres over asyncpg, but Alembic runs its
    migrations synchronously, so swap the async driver for psycopg2. The rest
    of the DSN (user, password, host, port, database) is unchanged, so each
    service still points at its own database via its own DATABASE_URL.
    """
    return os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live (sync) connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()

    connectable = engine_from_config(
        configuration,
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
