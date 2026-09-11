import logging
from collections.abc import Mapping
from dataclasses import dataclass, field

from ai_document_plugin_service.ai.common.types import AssignmentStats


@dataclass(frozen=True)
class PipelineMetricStep:
    name: str
    stats: AssignmentStats


@dataclass(frozen=True)
class PipelineStats:
    """Totals across all pipeline steps for a single run."""

    llm_calls: int
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float


@dataclass
class PipelineMetricsCollector:
    steps: list[PipelineMetricStep] = field(default_factory=list)

    def add_step(self, step_name: str, stats: AssignmentStats | None) -> None:
        if stats is None:
            return
        self.steps.append(PipelineMetricStep(name=step_name, stats=stats))

    def get_totals(self, elapsed_seconds: float) -> PipelineStats:
        return PipelineStats(
            llm_calls=self.total_llm_calls,
            input_tokens=self.total_input_tokens,
            output_tokens=self.total_output_tokens,
            elapsed_seconds=elapsed_seconds,
        )

    def log_summary(self, logger: logging.Logger) -> None:
        if not self.steps:
            logger.debug('No pipeline metrics were collected.')
            return

        logger.debug('Token usage:')
        for step in self.steps:
            logger.debug(
                '%s: %s calls, %s in / %s out tokens',
                step.name,
                f'{step.stats.total_calls:,}',
                f'{step.stats.total_input_tokens:,}',
                f'{step.stats.total_output_tokens:,}',
            )

        logger.debug(
            'Total: %s calls, %s in / %s out tokens',
            f'{self.total_llm_calls:,}',
            f'{self.total_input_tokens:,}',
            f'{self.total_output_tokens:,}',
        )

    @property
    def total_llm_calls(self) -> int:
        return sum(step.stats.total_calls for step in self.steps)

    @property
    def total_input_tokens(self) -> int:
        return sum(step.stats.total_input_tokens for step in self.steps)

    @property
    def total_output_tokens(self) -> int:
        return sum(step.stats.total_output_tokens for step in self.steps)


def _get_component_dict(
    pipeline_result: Mapping[str, object],
    component_name: str,
) -> dict[str, object] | None:
    component_result = pipeline_result.get(component_name)
    if not isinstance(component_result, dict):
        return None
    return {str(key): value for key, value in component_result.items()}


def get_component_stats(
    pipeline_result: Mapping[str, object],
    component_name: str,
) -> AssignmentStats | None:
    component_result = _get_component_dict(pipeline_result, component_name)
    if component_result is None:
        return None
    stats = component_result.get('stats')
    if isinstance(stats, AssignmentStats):
        return stats
    return None


def get_component_markdown(
    pipeline_result: Mapping[str, object],
    component_name: str,
) -> str | None:
    component_result = _get_component_dict(pipeline_result, component_name)
    if component_result is None:
        return None
    markdown = component_result.get('markdown')
    if isinstance(markdown, str):
        return markdown
    return None
