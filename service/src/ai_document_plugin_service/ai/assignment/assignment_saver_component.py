import json
import logging
import pathlib

from ai_document_plugin_service.ai.assignment.types import SectionAssignment
from ai_document_plugin_service.ai.common.types import AssignmentStats

from haystack import component

logger = logging.getLogger(__name__)


@component
class AssignmentSaverComponent:
    @component.output_types(assignments=list[SectionAssignment], stats=AssignmentStats)
    def run(self,
        assignments: list[SectionAssignment],
        output_path: str,
        stats: AssignmentStats | None = None,
    ):
        """Save assignments to JSON, optionally including token usage stats."""
        serializable = [assignment.to_dict() for assignment in assignments]
        if stats is None:
            payload = serializable
        else:
            payload = {
                'assignments': serializable,
                'stats': {
                    'total_calls': stats.total_calls,
                    'total_input_tokens': stats.total_input_tokens,
                    'total_output_tokens': stats.total_output_tokens,
                },
            }

        with pathlib.Path(output_path).open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        logger.debug('Saved assignments to %s', output_path)

        return {
            "assignments": assignments,
            "stats": stats
        }

