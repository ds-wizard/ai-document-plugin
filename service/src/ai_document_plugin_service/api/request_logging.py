import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import fastapi
from starlette.types import Message

from ai_document_plugin_service.ai.common.logging_payloads import summarize_headers, summarize_http_body
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

        response_body = await _read_response_body(response)
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
        response_body_summary = summarize_http_body(
            response_body,
            content_type=response.headers.get('content-type'),
        )
        if response_body_summary is not None:
            logger.debug(
                'HTTP response body',
                extra={
                    'url.path': request.url.path,
                    'http.response.body': response_body_summary,
                    'http.response.status_code': response.status_code,
                },
            )

    response.headers[TRACE_UUID_HEADER] = trace_uuid
    return _rebuild_response(response, response_body)


def _restore_request_body(request: fastapi.Request, body: bytes) -> None:
    async def receive() -> Message:
        return {
            'type': 'http.request',
            'body': body,
        }

    request._receive = receive


async def _read_response_body(response: fastapi.Response) -> bytes:
    body = b''
    async for chunk in response.body_iterator:
        body += chunk
    return body


def _rebuild_response(response: fastapi.Response, body: bytes) -> fastapi.Response:
    return fastapi.Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )
