import json
import pathlib

from ai_document_plugin_service.ai.assignment.types import SectionAssignment
from ai_document_plugin_service.ai.common.types import AssignmentStats


def save_assignments(
    assignments: list[SectionAssignment],
    output_path: str,
    stats: AssignmentStats | None = None,
) -> None:
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
