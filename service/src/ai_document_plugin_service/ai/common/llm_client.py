import logging
import time
from typing import Callable, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from ai.common import AssignmentStats

T = TypeVar("T")
logger = logging.getLogger(__name__)


def call_with_retry(fn: Callable[[], T], max_retries: int = 3, delay: float = 2.0) -> T:
    """Retry fn on connection or rate-limit errors."""
    err = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err = e
            if attempt < max_retries - 1:
                logger.debug("Error calling LLM, retrying: %s", e)
                time.sleep(delay)
    raise err


def extract_usage_tokens(response) -> tuple[int, int]:
    """
    :param response:
    :return: Input tokens, Output tokens
    """
    usage = getattr(response, "usage", None)
    if usage:
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)
        if input_tokens is not None and output_tokens is not None:
            return input_tokens, output_tokens
    raise Exception("No token info provided in the API response")


def add_usage(stats: "AssignmentStats", response) -> None:
    if stats is None:
        return
    input_tokens, output_tokens = extract_usage_tokens(response)
    stats.total_calls += 1
    stats.total_input_tokens += input_tokens
    stats.total_output_tokens += output_tokens
