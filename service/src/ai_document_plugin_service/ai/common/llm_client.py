import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.common import AssignmentStats

logger = logging.getLogger(__name__)


def call_with_retry[T](
    fn: Callable[[], T],
    max_retries: int = 3,
    delay: float = 2.0,
) -> T:
    """Retry fn on connection or rate-limit errors."""
    err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err = e
            if attempt < max_retries - 1:
                logger.debug('Error calling LLM, retrying: %s', e)
                time.sleep(delay)
    if err is not None:
        raise err
    msg = 'call_with_retry finished without result or exception'
    raise RuntimeError(msg)


def extract_usage_tokens(response: Any) -> tuple[int, int]:
    """:param response:
    :return: Input tokens, Output tokens
    """
    usage = getattr(response, 'usage', None)
    if usage:
        input_tokens = getattr(usage, 'prompt_tokens', None)
        output_tokens = getattr(usage, 'completion_tokens', None)
        if input_tokens is not None and output_tokens is not None:
            return input_tokens, output_tokens
    msg = 'No token info provided in the API response'
    raise Exception(msg)


def add_usage(stats: 'AssignmentStats | None', response: Any) -> None:
    if stats is None:
        return
    input_tokens, output_tokens = extract_usage_tokens(response)
    stats.total_calls += 1
    stats.total_input_tokens += input_tokens
    stats.total_output_tokens += output_tokens
