import logging
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.types.chat import ChatCompletion

from ai_document_plugin_service.ai.common.dynamic_semaphore import DynamicSemaphore

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.common import AssignmentStats

logger = logging.getLogger(__name__)
semaphore = DynamicSemaphore(1)


class MissingTokenUsageError(ValueError):
    """Raised when a model response has no usage token information."""


def call_with_retry[T](
    fn: Callable[[], T],
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
            return fn()
        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            err = e
            if attempt < max_retries - 1:
                logger.warning('Error calling LLM, retrying: %s', e)
                time.sleep(delay)
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
    def __init__(self, model: str, api_key: str, api_url: str, parallel_workers: int | None) -> None:
        self.client = OpenAI(api_key=api_key, base_url=api_url, max_retries=0)
        self.model = model
        self.max_workers = parallel_workers or 1
        logger.debug(
            'Initializing LLM client, setting semaphore limit to %s',
            self.max_workers,
        )
        semaphore.set_limit(self.max_workers)

    def get_max_workers(self):
        return self.max_workers

    def get_model_name(self):
        return self.model

    def completion(
        self,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatCompletion:
        req_id = uuid.uuid4().hex[:8]
        wait_start = time.perf_counter()
        logger.debug(
            '[llm] req=%s model=%s queueing (semaphore active/limit unknown until acquire)',
            req_id,
            self.model,
        )
        with semaphore:
            wait_s = time.perf_counter() - wait_start
            logger.debug(
                '[llm] req=%s acquired semaphore after %.3fs (limit=%s)',
                req_id,
                wait_s,
                semaphore.limit,
            )
            call_start = time.perf_counter()
            result = self.client.chat.completions.create(model=self.model, *args, **kwargs)
            logger.debug(
                '[llm] req=%s completed in %.3fs (releasing semaphore)',
                req_id,
                time.perf_counter() - call_start,
            )
            return result
