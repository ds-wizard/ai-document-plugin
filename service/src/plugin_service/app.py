import fastapi
import fastapi.middleware.cors
import fastapi.responses


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(
        title='Plugin Service',
        version='1.0.0',
    )

    app.add_middleware(
        middleware_class=fastapi.middleware.cors.CORSMiddleware,  # type: ignore
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/health')
    async def health_check() -> fastapi.responses.JSONResponse:
        return fastapi.responses.JSONResponse(content={'status': 'healthy'})

    return app
