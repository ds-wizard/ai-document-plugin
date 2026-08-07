import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import fastapi
from starlette.types import Message

from ai_document_plugin_service.ai.common.logging_payloads import summarize_headers, summarize_http_body

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = 'X-Request-ID'


async def log_http_request_response(
    request: fastapi.Request,
    call_next: Callable[[fastapi.Request], Awaitable[fastapi.Response]],
) -> fastapi.Response:
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    request.state.request_id = request_id
    request_body = await request.body()
    _restore_request_body(request, request_body)

    logger.info(
        'HTTP request started',
        extra={
            'request.id': request_id,
            'http.request.method': request.method,
            'url.path': request.url.path,
            'url.query': request.url.query,
            'client.address': request.client.host if request.client else None,
            'client.port': request.client.port if request.client else None,
            'http.request.headers': summarize_headers(dict(request.headers)),
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
                'request.id': request_id,
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
                'request.id': request_id,
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
            'request.id': request_id,
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
                'request.id': request_id,
                'url.path': request.url.path,
                'http.response.body': response_body_summary,
                'http.response.status_code': response.status_code,
            },
        )

    response.headers[REQUEST_ID_HEADER] = request_id
    return _rebuild_response(response, response_body)


def _restore_request_body(request: fastapi.Request, body: bytes) -> None:
    async def receive() -> Message:  # noqa: RUF029
        return {
            'type': 'http.request',
            'body': body,
            'more_body': False,
        }

    request._receive = receive  # type: ignore[method-assign]  # noqa: SLF001


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
