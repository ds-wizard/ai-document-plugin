import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletion

from ai_document_plugin_service.ai.common.dynamic_semaphore import DynamicSemaphore

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.common import AssignmentStats

logger = logging.getLogger(__name__)


class InvalidLLMConfigError(ValueError):
    def __init__(self, var_name: str, tenant: str) -> None:
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

    def __init__(self, tenant_uuid: str) -> None:
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
        logger.debug(
            '[llm] tenant=%s: Updated LLM client config, setting semaphore limit to %s',
            self.tenant_uuid,
            self.max_workers,
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
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatCompletion:
        if self.model is None:
            raise InvalidLLMConfigError('model', self.tenant_uuid)  # noqa: EM101
        if self.max_workers is None:
            raise InvalidLLMConfigError('max_workers', self.tenant_uuid)  # noqa: EM101
        if self.api_url is None:
            raise InvalidLLMConfigError('api_url', self.tenant_uuid)  # noqa: EM101
        if self.api_key is None:
            raise InvalidLLMConfigError('api_key', self.tenant_uuid)  # noqa: EM101
        if self.client is None:
            msg = f'LLM internal client is null but api_key and api_url is set for tenant {self.tenant_uuid}.'
            raise RuntimeError(msg)
        req_id = uuid.uuid4().hex[:8]
        wait_start = time.perf_counter()
        logger.debug('[llm] req=%s model=%s queueing', req_id, self.model)
        async with self.semaphore:
            wait_s = time.perf_counter() - wait_start
            logger.debug(
                '[llm] req=%s acquired semaphore after %.3fs (limit=%s)',
                req_id,
                wait_s,
                self.semaphore.limit,
            )
            call_start = time.perf_counter()
            result = await self.client.chat.completions.create(*args, model=self.model, **kwargs)
            logger.debug(
                '[llm] req=%s completed in %.3fs (releasing semaphore)',
                req_id,
                time.perf_counter() - call_start,
            )
            return result
