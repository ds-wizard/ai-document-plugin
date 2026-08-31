import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletion

from ai_document_plugin_service.ai.common.dynamic_semaphore import DynamicSemaphore
from ai_document_plugin_service.ai.common.execution_logging import log_llm_event

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.common import AssignmentStats

logger = logging.getLogger(__name__)


class InvalidLLMConfigError(ValueError):
    def __init__(self, var_name: str, tenant: uuid.UUID) -> None:
        super().__init__(
            f"LLM '{var_name}' for tenant {tenant} is None, did you call `update_config` before using the client?"
        )


class MissingTokenUsageError(ValueError):
    """Raised when a model response has no usage token information."""


async def call_with_retry[T](
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    delay: float = 2.0,
) -> T:
    """Retry fn on transient OpenAI network/rate-limit errors.

    Raises:
        RuntimeError: If no result or exception is produced by the retry loop.
    """
    err: APIConnectionError | APITimeoutError | RateLimitError | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            err = exc
            if attempt < max_retries - 1:
                logger.warning('Error calling LLM, retrying: %s', exc)
                await asyncio.sleep(delay)
    if err is not None:
        raise err
    msg = 'call_with_retry finished without result or exception'
    raise RuntimeError(msg)


def extract_usage_tokens(response: object) -> tuple[int, int]:
    """Extract prompt/completion token counts from a model response.

    Args:
        response: OpenAI response object that may include `usage`.

    Returns:
        Tuple of `(input_tokens, output_tokens)`.

    Raises:
        MissingTokenUsageError: If token usage is not present on the response.
    """
    usage = getattr(response, 'usage', None)
    if usage:
        input_tokens = getattr(usage, 'prompt_tokens', None)
        output_tokens = getattr(usage, 'completion_tokens', None)
        if input_tokens is not None and output_tokens is not None:
            return input_tokens, output_tokens
    msg = 'No token info provided in the API response'
    logger.error('LLM response is missing token usage information')
    raise MissingTokenUsageError(msg)


def add_usage(stats: 'AssignmentStats | None', response: object) -> None:
    if stats is None:
        return
    input_tokens, output_tokens = extract_usage_tokens(response)
    stats.add_usage(input_tokens, output_tokens)


class LLMClient:
    """
    LLM Client for calling llm server using the OpenAI API standard.
    It is able to update its config on the run.

    There should always be at most one instance of llm client per tenant!
    This is because LLM client handles throttling to avoid spamming the LLM API.
    """

    def __init__(self, tenant_uuid: uuid.UUID) -> None:
        """
        Initializes the client with empty config. Call update_config before using it.
        """
        self.tenant_uuid = tenant_uuid
        self.model = None
        self.max_workers = None
        self.semaphore = DynamicSemaphore(1)
        self.api_key = None
        self.api_url = None
        self.client: AsyncOpenAI | None = None

    def update_config(self, model: str, api_key: str, api_url: str, parallel_workers: int | None) -> None:
        """
        Changes LLMClient config. Can be called even while this class is being used in parallel by asyncio elsewhere.
        If all inputs are the same as they were, nothing updates.
        :param model: updated model name (or the previous)
        :param api_key: updated api_key
        :param api_url: updated api_url
        :param parallel_workers: updated parallel workers. If worker count is being reduced, it may take a while before
            the llm client reaches the reduced state. This is because when going for example from 8 to 5 workers,
            LLMClient does not kill any requests, instead, it stops queueing new requests until the 3 extra requests
            finish running.
        :return:
        """
        if (
            self.model == model
            and self.api_key == api_key
            and self.api_url == api_url
            and self.max_workers == parallel_workers
        ):
            # nothing has changed, we can return
            return
        self.model = model
        self.api_key = api_key
        self.api_url = api_url
        self.max_workers = max(1, parallel_workers or 1)
        self.semaphore.set_limit(self.max_workers)
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_url, max_retries=0)
        logger.info(
            'LLM client configuration updated',
            extra={
                'tenant_uuid': str(self.tenant_uuid),
                'llm_model': self.model,
                'llm_max_workers': self.max_workers,
            },
        )

    def get_max_workers(self) -> int:
        if self.max_workers is None:
            msg = 'max_workers is None for tenant %s. `get_max_workers` was accessed before calling update_config'
            raise RuntimeError(msg, self.tenant_uuid)
        return self.max_workers

    def get_model_name(self) -> str:
        if self.model is None:
            msg = 'model is None for tenant %s. `get_model_name` was accessed before calling update_config'
            raise RuntimeError(msg, self.tenant_uuid)
        return self.model

    async def completion(
        self,
        *args: Any,  # noqa: ANN401
        stats: 'AssignmentStats | None' = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatCompletion:
        if self.model is None:
            logger.error('LLM completion failed: model is not configured',
                         extra={'tenant_uuid': str(self.tenant_uuid)})
            raise InvalidLLMConfigError('model', self.tenant_uuid)  # noqa: EM101
        if self.max_workers is None:
            logger.error('LLM completion failed: max_workers is not configured',
                         extra={'tenant_uuid': str(self.tenant_uuid)})
            raise InvalidLLMConfigError('max_workers', self.tenant_uuid)  # noqa: EM101
        if self.api_url is None:
            logger.error('LLM completion failed: api_url is not configured',
                         extra={'tenant_uuid': str(self.tenant_uuid)})
            raise InvalidLLMConfigError('api_url', self.tenant_uuid)  # noqa: EM101
        if self.api_key is None:
            logger.error('LLM completion failed: api_key is not configured',
                         extra={'tenant_uuid': str(self.tenant_uuid)})
            raise InvalidLLMConfigError('api_key', self.tenant_uuid)  # noqa: EM101
        if self.client is None:
            msg = f'LLM internal client is null but api_key and api_url is set for tenant {self.tenant_uuid}.'
            logger.error('LLM completion failed: internal AsyncOpenAI client is missing',
                         extra={'tenant_uuid': str(self.tenant_uuid)})
            raise RuntimeError(msg)
        req_id = uuid.uuid4().hex[:8]
        wait_start = time.perf_counter()
        log_llm_event(
            {
                'state': 'waiting_for_semaphore',
                'req_id': req_id,
                'tenant_uuid': str(self.tenant_uuid),
                'model': self.model,
                'limit': self.semaphore.limit,
                'active_count': self.semaphore.active_count,
                'queued_count': self.semaphore.queued_count + 1,
            },
        )
        async with self.semaphore:
            wait_s = time.perf_counter() - wait_start
            log_llm_event(
                {
                    'state': 'waiting_for_llm_response',
                    'req_id': req_id,
                    'tenant_uuid': str(self.tenant_uuid),
                    'model': self.model,
                    'limit': self.semaphore.limit,
                    'active_count': self.semaphore.active_count,
                    'queued_count': self.semaphore.queued_count,
                    'semaphore_wait_ms': _duration_ms(wait_s),
                    'message_count': _count_messages(kwargs.get('messages')),
                },
            )
            call_start = time.perf_counter()
            try:
                result = await self.client.chat.completions.create(*args, model=self.model, **kwargs)
            except Exception as error:
                duration_s = time.perf_counter() - call_start
                _add_timing(stats, wait_s, duration_s)
                self._log_llm_completion(
                    req_id=req_id,
                    status='error',
                    wait_s=wait_s,
                    duration_s=duration_s,
                    request_kwargs=kwargs,
                    error=error,
                )
                raise

            duration_s = time.perf_counter() - call_start
            _add_timing(stats, wait_s, duration_s)
            self._log_llm_completion(
                req_id=req_id,
                status='success',
                wait_s=wait_s,
                duration_s=duration_s,
                request_kwargs=kwargs,
                response=result,
            )
            return result

    def _log_llm_completion(
        self,
        *,
        req_id: str,
        status: str,
        wait_s: float,
        duration_s: float,
        request_kwargs: dict[str, Any],
        response: ChatCompletion | None = None,
        error: Exception | None = None,
    ) -> None:
        payload = {
            'state': 'completed' if status == 'success' else 'failed',
            'status': status,
            'req_id': req_id,
            'tenant_uuid': str(self.tenant_uuid),
            'model': self.model,
            'semaphore_wait_ms': _duration_ms(wait_s),
            'llm_response_ms': _duration_ms(duration_s),
            'total_llm_ms': _duration_ms(wait_s + duration_s),
            'message_count': _count_messages(request_kwargs.get('messages')),
            'temperature': request_kwargs.get('temperature'),
            'max_tokens': request_kwargs.get('max_tokens'),
            'reasoning_effort': request_kwargs.get('reasoning_effort'),
        }
        if response is not None:
            usage = _extract_usage(response)
            payload.update(
                finish_reason=response.choices[0].finish_reason if response.choices else None,
                prompt_tokens=usage['prompt_tokens'],
                completion_tokens=usage['completion_tokens'],
                total_tokens=usage['total_tokens'],
            )
        if error is not None:
            payload.update(
                {
                    'error_type': type(error).__name__,
                    'error_message': str(error),
                },
            )
        log_llm_event(payload)


def _count_messages(messages: object) -> int | None:
    if isinstance(messages, list):
        return len(messages)
    return None


def _duration_ms(duration_s: float) -> float:
    return round(duration_s * 1000, 3)


def _add_timing(stats: 'AssignmentStats | None', wait_s: float, duration_s: float) -> None:
    if stats is None:
        return
    stats.add_llm_timing(
        wait_ms=_duration_ms(wait_s),
        response_ms=_duration_ms(duration_s),
    )


def _extract_usage(response: ChatCompletion) -> dict[str, int | None]:
    usage = getattr(response, 'usage', None)
    return {
        'prompt_tokens': getattr(usage, 'prompt_tokens', None),
        'completion_tokens': getattr(usage, 'completion_tokens', None),
        'total_tokens': getattr(usage, 'total_tokens', None),
    }
