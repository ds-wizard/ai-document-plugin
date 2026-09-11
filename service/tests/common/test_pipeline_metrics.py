import time

from ai_document_plugin_service.ai.common.pipeline_metrics import (
    get_component_markdown,
    get_component_stats,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats


def test_get_component_stats_returns_value_for_component_output() -> None:
    result = {
        'component_a': {
            'stats': AssignmentStats(total_calls=1),
        },
    }

    output = get_component_stats(result, 'component_a')

    assert output is not None
    assert output.total_calls == 1


def test_get_component_stats_returns_none_when_missing() -> None:
    assert get_component_stats({}, 'component_a') is None


def test_get_component_markdown_returns_value_for_component_output() -> None:
    result = {
        'component_a': {
            'markdown': '# DMP',
        },
    }

    output = get_component_markdown(result, 'component_a')

    assert output == '# DMP'
