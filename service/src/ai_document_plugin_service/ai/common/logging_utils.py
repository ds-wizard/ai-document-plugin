import logging

def configure_logging(level: int | str = logging.DEBUG) -> None:
    normalized_level = _normalize_level(level)
    _configure_root_stdout_logging(normalized_level)
    _configure_library_log_levels()


def _normalize_level(level: int | str) -> int:
    if isinstance(level, str):
        normalized_level = logging.getLevelName(level.upper())
        if not isinstance(normalized_level, int):
            msg = f'Unsupported log level: {level}'
            raise TypeError(msg)
        return normalized_level
    return level


def _configure_root_stdout_logging(level: int) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        )


def _configure_library_log_levels() -> None:
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
