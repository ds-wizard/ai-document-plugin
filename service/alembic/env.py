from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ai_document_plugin_service.ai.common.config import load_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _get_database_settings() -> tuple[str, str]:
    app_config = load_config()
    database = app_config.database
    url = (
        f'postgresql+psycopg://{database.user}:{database.password}'
        f'@{database.host}:{database.port}/{database.name}'
    )
    return url, database.schema


def run_migrations_offline() -> None:
    url, schema = _get_database_settings()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        version_table_schema=schema,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url, schema = _get_database_settings()
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = url

    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
