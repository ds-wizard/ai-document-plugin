from openai import APIStatusError, APIConnectionError

from ai_document_plugin_service.api.types import ErrorType

HTTP_INTERNAL_SERVER_ERROR = 500
STATUS_CODE_ERROR_TYPES = {
    401: ErrorType.LLM_AUTHENTICATION_FAILED,
    404: ErrorType.LLM_NOT_FOUND,
    429: ErrorType.LLM_RATE_LIMITED,
}

RETRYABLE_ERROR_TYPES = frozenset(
    {ErrorType.LLM_CONNECTION_FAILED, ErrorType.LLM_RATE_LIMITED, ErrorType.LLM_UNAVAILABLE})


class LLMError(Exception):
    """Raised when the call to the LLM API fails, carries the error shown to the user."""

    def __init__(self, error_type: ErrorType) -> None:
        self.error_type = error_type
        self.message = error_type.message
        self.retryable = error_type in RETRYABLE_ERROR_TYPES
        super().__init__(self.message)


def _status_code_error_type(status_code: int) -> ErrorType:
    if status_code in STATUS_CODE_ERROR_TYPES:
        return STATUS_CODE_ERROR_TYPES[status_code]
    if status_code >= HTTP_INTERNAL_SERVER_ERROR:
        return ErrorType.LLM_UNAVAILABLE
    return ErrorType.LLM_GENERAL_ERROR


def llm_error_from_exception(error: Exception) -> LLMError | None:
    """Classify the OpenAI client error only by its HTTP status code.

    Errors without a response are connection failures, other errors are not classified.
    """
    if isinstance(error, APIStatusError):
        return LLMError(_status_code_error_type(error.status_code))
    if isinstance(error, APIConnectionError):
        return LLMError(ErrorType.LLM_CONNECTION_FAILED)
    return None
