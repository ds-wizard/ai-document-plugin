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


def test_append_summary_adds_table_and_totals() -> None:
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

    markdown = collector.append_summary('# DMP', elapsed_seconds=12.5)

    assert '# DMP' in markdown
    assert '## Pipeline token usage and cost' in markdown
    assert '1. Step' in markdown
    assert '2. Step' in markdown
    assert '**Total**' in markdown
    assert '1500' in markdown
    assert '250' in markdown
    assert 'Total time: 12.5s' in markdown
