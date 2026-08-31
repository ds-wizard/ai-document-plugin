import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import fastapi
from starlette.types import Message

from ai_document_plugin_service.ai.common.logging_payloads import summarize_http_body
from ai_document_plugin_service.ai.common.trace_context import trace_context

logger = logging.getLogger(__name__)

TRACE_UUID_HEADER = 'X-Trace-UUID'


async def log_http_request_response(
    request: fastapi.Request,
    call_next: Callable[[fastapi.Request], Awaitable[fastapi.Response]],
) -> fastapi.Response:
    trace_uuid = str(uuid.uuid4())
    request.state.trace_uuid = trace_uuid
    request_body = await request.body()
    _restore_request_body(request, request_body)

    with trace_context(trace_uuid):
        logger.info(
            'HTTP request started',
            extra={
                'http.request.method': request.method,
                'url.path': request.url.path,
                'url.query': request.url.query,
            },
        )
        request_body_summary = summarize_http_body(
            request_body,
            content_type=request.headers.get('content-type'),
        )
        if request_body_summary is not None:
            logger.debug(
                'HTTP request body',
                extra={
                    'url.path': request.url.path,
                    'http.request.body': request_body_summary,
                },
            )

        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                'HTTP request failed with unhandled exception',
                extra={
                    'http.request.method': request.method,
                    'url.path': request.url.path,
                    'duration_ms': round((time.perf_counter() - started_at) * 1000, 3),
                },
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        logger.info(
            'HTTP request completed',
            extra={
                'http.request.method': request.method,
                'url.path': request.url.path,
                'http.response.status_code': response.status_code,
                'duration_ms': duration_ms,
            },
        )
    response.headers[TRACE_UUID_HEADER] = trace_uuid
    return response


def _restore_request_body(request: fastapi.Request, body: bytes) -> None:
    async def receive() -> Message:  # noqa: RUF029
        return {
            'type': 'http.request',
            'body': body,
        }

    request._receive = receive  # type: ignore[method-assign]  # noqa: SLF001
