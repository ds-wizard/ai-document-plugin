import logging

import fastapi
import fastapi.middleware.cors
from starlette.requests import Request
from starlette.responses import JSONResponse

from ai_document_plugin_service.ai.common import configure_logging
from ai_document_plugin_service.ai.common.config import load_config, resolve_config_path
from ai_document_plugin_service.ai.persistence.migrations import run_startup_migrations
from ai_document_plugin_service.api.request_logging import log_http_request_response
from ai_document_plugin_service.api.routes import protected_router, public_router
from ai_document_plugin_service.di import setup_app_state
from ai_document_plugin_service.service.errors import ServiceError

logger = logging.getLogger(__name__)


def create_app(*, run_migrations: bool = True) -> fastapi.FastAPI:
    config_path = resolve_config_path()
    config = load_config(config_path)
    configure_logging(config.log_level)

    if run_migrations:
        run_startup_migrations(config, config_path)

    app = fastapi.FastAPI(title='Plugin Service', version='1.0.0')
    setup_app_state(app, config)
    app.middleware('http')(log_http_request_response)

    @app.exception_handler(ServiceError)
    def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        logger.error(
            'API request rejected',
            extra={
                'http.request.method': request.method,
                'url.path': request.url.path,
                'http.response.status_code': exc.status_code,
                'error_type': type(exc).__name__,
                'error_message': exc.detail,
            },
        )
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})

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
