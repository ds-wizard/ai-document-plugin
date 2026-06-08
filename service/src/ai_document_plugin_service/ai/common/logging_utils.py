import logging


def configure_logging(level: int | str = logging.DEBUG) -> None:
    if isinstance(level, str):
        normalized_level = logging.getLevelName(level.upper())
        if not isinstance(normalized_level, int):
            msg = f'Unsupported log level: {level}'
            raise TypeError(msg)
        level = normalized_level

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        return

    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
