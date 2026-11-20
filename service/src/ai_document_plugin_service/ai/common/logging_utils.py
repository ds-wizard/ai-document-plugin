import logging
from dataclasses import asdict
from typing import override
from uuid import UUID

from ai_document_plugin_service.ai.common.run_context import get_run_log_context
from ai_document_plugin_service.ai.common.trace_context import get_trace_uuid

LOG_FORMAT = '%(asctime)s | %(levelname)8s | %(name)s: [T:%(traceId)s] %(message)s'
_ORIGINAL_LOG_RECORD_FACTORY = logging.getLogRecordFactory()
_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {'asctime', 'message', 'traceId'}


class RunContextFilter(logging.Filter):
    """Adds the identifiers of the pipeline run in progress to every log record under ``context``.

    A ``context`` a log call passes explicitly through ``extra`` is kept as it is.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        context = get_run_log_context()
        if context is not None and not hasattr(record, 'context'):
            record.context = {field: str(value) for field, value in asdict(context).items() if value is not None}
        return True


class ExtraFormatter(logging.Formatter):
    """Appends application fields supplied through ``extra`` to text logs."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        extra = {
            key: str(value) if isinstance(value, UUID) else value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_FIELDS
        }
        return f'{formatted} | extra={extra!r}' if extra else formatted


def configure_logging(level: int | str = logging.DEBUG) -> None:
    normalized_level = _normalize_level(level)
    _configure_root_stdout_logging(normalized_level)
    _configure_library_log_levels()


def _normalize_level(level: int | str) -> int:
    if isinstance(level, str):
        normalized_level = logging.getLevelNamesMapping().get(level.upper())
        if not isinstance(normalized_level, int):
            msg = f'Unsupported log level: {level}'
            raise TypeError(msg)
        return normalized_level
    return level


def _configure_root_stdout_logging(level: int) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _install_trace_log_record_factory()

    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format=LOG_FORMAT,
        )

    for handler in root_logger.handlers:
        handler.setLevel(level)
        handler.setFormatter(ExtraFormatter(LOG_FORMAT))
        if not any(isinstance(log_filter, RunContextFilter) for log_filter in handler.filters):
            handler.addFilter(RunContextFilter())


def _configure_library_log_levels() -> None:
    logging.getLogger('haystack').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)


def _install_trace_log_record_factory() -> None:
    current_factory = logging.getLogRecordFactory()
    if current_factory is _trace_log_record_factory:
        return
    logging.setLogRecordFactory(_trace_log_record_factory)


def _trace_log_record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _ORIGINAL_LOG_RECORD_FACTORY(*args, **kwargs)
    trace_id = get_trace_uuid()
    record.traceId = '-' if trace_id is None else str(trace_id)
    return record
