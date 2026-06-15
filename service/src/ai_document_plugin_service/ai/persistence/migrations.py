import logging
import pathlib

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from ai_document_plugin_service.ai.common.config import Config, DatabaseConfig

logger = logging.getLogger(__name__)

_MIGRATION_LOCK_KEYS = (20260521, 1)


def run_startup_migrations(app_config: Config, config_path: str) -> None:
    database_url = _create_database_url(app_config.database)
    engine = create_engine(database_url, poolclass=NullPool)

    try:
        with engine.connect() as connection:
            logger.info('Verifying database connection before running migrations')
            connection.execute(text('SELECT 1'))
            connection.commit()

            logger.info('Acquiring database migration lock')
            connection.execute(
                text('SELECT pg_advisory_lock(:key_1, :key_2)'),
                {'key_1': _MIGRATION_LOCK_KEYS[0], 'key_2': _MIGRATION_LOCK_KEYS[1]},
            )
            connection.commit()

            try:
                alembic_config = _create_alembic_config(app_config, config_path)
                alembic_config.attributes['connection'] = connection
                logger.info('Running Alembic migrations')
                command.upgrade(alembic_config, 'head')
                logger.info('Alembic migrations are up to date')
            finally:
                if connection.in_transaction():
                    connection.rollback()
                connection.execute(
                    text('SELECT pg_advisory_unlock(:key_1, :key_2)'),
                    {'key_1': _MIGRATION_LOCK_KEYS[0], 'key_2': _MIGRATION_LOCK_KEYS[1]},
                )
                connection.commit()
                logger.info('Released database migration lock')
    finally:
        engine.dispose()


def _create_database_url(database: DatabaseConfig) -> URL:
    return URL.create(
        drivername='postgresql+psycopg',
        username=database.user,
        password=database.password,
        host=database.host,
        port=database.port,
        database=database.name,
    )


def _create_alembic_config(app_config: Config, config_path: str) -> AlembicConfig:
    alembic_config = AlembicConfig()
    alembic_config.set_main_option('script_location', str(_resolve_migrations_dir()))
    alembic_config.attributes['app_config'] = app_config
    alembic_config.attributes['config_path'] = config_path
    return alembic_config


def _resolve_migrations_dir() -> pathlib.Path:
    migrations_dir = pathlib.Path(__file__).resolve().parents[2] / 'migrations'

    if (migrations_dir / 'env.py').is_file() and (migrations_dir / 'versions').is_dir():
        return migrations_dir

    msg = 'Could not locate packaged Alembic migrations for startup database migration.'
    raise RuntimeError(msg)
