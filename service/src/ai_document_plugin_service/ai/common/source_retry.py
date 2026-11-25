"""Bounded LLM repair attempts for invalid statement sources."""

import logging
from collections.abc import Awaitable, Callable

from ai_document_plugin_service.ai.common.source_ids import SourceValidationError, validate_source_ids

logger = logging.getLogger(__name__)
_MAX_SOURCE_REPAIRS = 2


async def generate_with_valid_sources(
    generate: Callable[[str], Awaitable[str]],
    allowed_ids: set[str],
    *,
    require_sources: bool = False,
) -> str:
    """Make one request and at most two repairs; retry only source validation errors.

    Raises:
        SourceValidationError: The last repair still contains invalid sources.
    """
    feedback = ''
    for attempt in range(_MAX_SOURCE_REPAIRS + 1):
        markdown = await generate(feedback)
        require_sources = require_sources or '<statement' in markdown
        try:
            validate_source_ids(markdown, allowed_ids, require_sources=require_sources)
        except SourceValidationError as error:
            logger.warning('Source validation failed', extra={'attempt': attempt + 1, 'error': str(error)})
            if attempt == _MAX_SOURCE_REPAIRS:
                raise
            feedback = (
                f'Source validation failed: {error}\n'
                f'Allowed source IDs: {" ".join(sorted(allowed_ids)) or "(none)"}.\n'
                'Repair the draft below using the original input above as the source of truth. '
                'Return the complete corrected document, preserving its facts and structure. '
                'Copy only IDs supporting each statement in the original input; never guess, renumber, '
                'or replace an unknown ID with an arbitrary allowed ID. '
                'Do not remove annotations to bypass validation.\n'
                f'Invalid draft:\n{markdown}'
            )
        else:
            return markdown
    msg = 'Source repair attempts exhausted'
    raise SourceValidationError(msg)
