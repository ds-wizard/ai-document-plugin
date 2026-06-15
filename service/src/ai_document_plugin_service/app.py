from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import fastapi
import fastapi.middleware.cors

from ai_document_plugin_service.ai.common.config import Config, load_config, resolve_config_path
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.ai.persistence.migrations import run_startup_migrations
from ai_document_plugin_service.api.routes import protected_router, public_router


@asynccontextmanager
async def _lifespan(app: fastapi.FastAPI) -> AsyncIterator[None]:
    config: Config = app.state.config
    app.state.database = PostgresDB(config.database)
    try:
        yield
    finally:
        app.state.database.engine.dispose()


def create_app(*, run_migrations: bool = True) -> fastapi.FastAPI:
    config_path = resolve_config_path()
    config = load_config(config_path)

    if run_migrations:
        run_startup_migrations(config, config_path)

    app = fastapi.FastAPI(title='Plugin Service', version='1.0.0', lifespan=_lifespan)
    app.state.config = config
    app.state.config_path = config_path
    app.add_middleware(
        middleware_class=fastapi.middleware.cors.CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(public_router)
    app.include_router(protected_router)
    return app


# Useful for debugging, otherwise it is better to run the app using make dev
if __name__ == '__main__':
    import uvicorn

    uvicorn.run(create_app(), host='0.0.0.0', port=8010)  # noqa: S104
