from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool
from sqlalchemy.engine import URL, Connection

from ai_document_plugin_service.ai.common.config import Config, load_config
from ai_document_plugin_service.ai.persistence.schema import create_persistence_schema

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_app_config() -> Config:
    app_config = config.attributes.get('app_config')
    if app_config is not None:
        return app_config

    return load_config(config.attributes.get('config_path'))


def _get_database_settings() -> tuple[str, str]:
    app_config = _get_app_config()
    database = app_config.database
    url = URL.create(
        drivername='postgresql+psycopg',
        username=database.user,
        password=database.password,
        host=database.host,
        port=database.port,
        database=database.name,
    )
    return url.render_as_string(hide_password=False), database.schema


def _get_target_metadata() -> MetaData:
    _, schema = _get_database_settings()
    persistence_schema = create_persistence_schema(schema)
    return persistence_schema.metadata


def run_migrations_offline() -> None:
    url, schema = _get_database_settings()
    context.configure(
        url=url,
        target_metadata=_get_target_metadata(),
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        version_table_schema=schema,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_with_connection(connection: Connection) -> None:
    _, schema = _get_database_settings()
    context.configure(
        connection=connection,
        target_metadata=_get_target_metadata(),
        version_table_schema=schema,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get('connection')
    if connection is not None:
        _run_migrations_with_connection(connection)
        return

    url, _ = _get_database_settings()
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = url

    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _run_migrations_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
