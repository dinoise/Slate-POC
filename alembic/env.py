"""Alembic environment configuration for async migrations."""

import asyncio
import os
from logging.config import fileConfig

from geoalchemy2 import alembic_helpers
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Solo importamos Base (modelos) — no instanciamos Settings completo.
# DATABASE_URL se lee directamente de la variable de entorno para que
# Alembic no dependa de REDIS_URL, SECRET_KEY ni ningún otro campo de app.
from slate_api.models.base import Base

_DATABASE_URL = os.environ["DATABASE_URL"]  # falla rápido si no está definida

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=False,
        compare_type=True,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


# Tables that belong to our models - everything else reflected from DB is ignored
_OUR_TABLES = {t.name for t in target_metadata.sorted_tables}

# Known PostGIS schemas to exclude
_POSTGIS_SCHEMAS = {"tiger", "tiger_data", "topology"}

# Known PostGIS tables in public schema to exclude
_POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
}


def include_object(object, name, type_, reflected, compare_to):
    """Filter to only include our application tables, ignoring all PostGIS system objects.

    The key insight: use `reflected=True` to identify objects found in the DB
    but not in our models - these are PostGIS system tables that should be ignored.
    """
    # Exclude objects from PostGIS schemas
    schema = getattr(object, "schema", None)
    if schema in _POSTGIS_SCHEMAS:
        return False

    if type_ == "table":
        # Exclude known PostGIS tables in public schema
        if name in _POSTGIS_TABLES:
            return False
        # Exclude any table reflected from DB that's not in our models
        if reflected and name not in _OUR_TABLES:
            return False

    if type_ == "index":
        table = getattr(object, "table", None)
        if table is not None:
            table_schema = getattr(table, "schema", None)
            if table_schema in _POSTGIS_SCHEMAS:
                return False
            if table.name in _POSTGIS_TABLES:
                return False
            # Exclude indexes on tables not in our models
            if reflected and table.name not in _OUR_TABLES:
                return False

    return True


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        include_schemas=False,
        compare_type=True,
        compare_server_default=True,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
