import fastapi
import fastapi.middleware.cors

from ai_document_plugin_service.api import router


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(title='Plugin Service', version='1.0.0')
    app.add_middleware(
        middleware_class=fastapi.middleware.cors.CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(router)
    return app


# Useful for debugging, otherwise it is better to run the app using make dev
if __name__ == '__main__':
    import uvicorn

    uvicorn.run(create_app(), host='0.0.0.0', port=8010)  # noqa: S104
