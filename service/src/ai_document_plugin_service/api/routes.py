import logging

from ai_document_plugin_service.api.router_helper import unprotected_api_router

logger = logging.getLogger(__name__)

unprotected_healthcheck_router = unprotected_api_router()


@unprotected_healthcheck_router.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'healthy'}
