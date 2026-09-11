from ai_document_plugin_service.ai.common.pipeline_metrics import (
    PipelineMetricsCollector,
    PipelineStats,
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


def test_get_totals_sums_steps_and_passes_elapsed_seconds_through() -> None:
    collector = PipelineMetricsCollector()
    collector.add_step(
        '1. Step',
        AssignmentStats(total_calls=2, total_input_tokens=1000, total_output_tokens=200),
    )
    collector.add_step('2. Missing step', None)
    collector.add_step(
        '3. Step',
        AssignmentStats(total_calls=1, total_input_tokens=500, total_output_tokens=50),
    )

    totals = collector.get_totals(elapsed_seconds=12.5)

    assert [step.name for step in collector.steps] == ['1. Step', '3. Step']
    assert totals == PipelineStats(llm_calls=3, input_tokens=1500, output_tokens=250, elapsed_seconds=12.5)
