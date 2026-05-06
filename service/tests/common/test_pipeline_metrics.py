from collections.abc import Mapping
from typing import cast

from ai_document_plugin_service.ai.common.pipeline_metrics import (
    PipelineMetricsCollector,
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


def test_get_stats_returns_json_summary_with_expected_shape() -> None:
    collector = PipelineMetricsCollector(
        model_name='test-model',
        cost_per_mil_input=0.25,
        cost_per_mil_output=2.0,
    )
    collector.add_step(
        '1. Step',
        AssignmentStats(total_calls=2, total_input_tokens=1000, total_output_tokens=200),
    )
    collector.add_step(
        '2. Step',
        AssignmentStats(total_calls=1, total_input_tokens=500, total_output_tokens=50),
    )

    stats = collector.get_stats(elapsed_seconds=12.5)

    assert isinstance(stats, Mapping)
    typed_stats = cast(dict[str, object], stats)

    assert typed_stats['title'] == 'Pipeline token usage and cost'
    assert typed_stats['headers'] == [
        'Step',
        'LLM calls',
        'Input tokens',
        'Output tokens',
        'Cost (USD)',
    ]
    assert typed_stats['rows'] == [
        {
            'step': '1. Step',
            'llm_calls': 2,
            'input_tokens': 1000,
            'output_tokens': 200,
            'cost_usd': 0.0,
        },
        {
            'step': '2. Step',
            'llm_calls': 1,
            'input_tokens': 500,
            'output_tokens': 50,
            'cost_usd': 0.0,
        },
    ]
    assert typed_stats['totals'] == {
        'input_tokens': 1500,
        'output_tokens': 250,
        'cost_usd': 0.0,
    }
    assert typed_stats['meta'] == {
        'model_name': 'test-model',
        'cost_per_mil_input': 0.25,
        'cost_per_mil_output': 2.0,
        'elapsed_seconds': 12.5,
    }
