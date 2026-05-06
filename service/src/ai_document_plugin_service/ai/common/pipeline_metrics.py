import logging
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass, field

from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.persistence.assignment_saver_component import JsonValue


@dataclass(frozen=True)
class PipelineMetricStep:
    name: str
    stats: AssignmentStats


@dataclass
class PipelineMetricsCollector:
    model_name: str
    cost_per_mil_input: float
    cost_per_mil_output: float
    steps: list[PipelineMetricStep] = field(default_factory=list)

    def add_step(self, step_name: str, stats: AssignmentStats | None) -> None:
        if stats is None:
            return
        self.steps.append(PipelineMetricStep(name=step_name, stats=stats))

    def get_stats(self, elapsed_seconds: float) -> JsonValue:
        return self._build_summary_section(elapsed_seconds)

    def log_summary(self, logger: logging.Logger) -> None:
        if not self.steps:
            logger.debug('No pipeline metrics were collected.')
            return

        logger.debug('Token usage and cost:')
        for step in self.steps:
            _, _, total_cost = self._price(step.stats)
            logger.debug(
                '%s: %s calls, %s in / %s out tokens, %.2f USD',
                step.name,
                f'{step.stats.total_calls:,}',
                f'{step.stats.total_input_tokens:,}',
                f'{step.stats.total_output_tokens:,}',
                total_cost,
            )

        logger.debug(
            'Total: %s in / %s out tokens, %.2f USD',
            f'{self.total_input_tokens:,}',
            f'{self.total_output_tokens:,}',
            self.total_cost,
        )

    @property
    def total_input_tokens(self) -> int:
        return sum(step.stats.total_input_tokens for step in self.steps)

    @property
    def total_output_tokens(self) -> int:
        return sum(step.stats.total_output_tokens for step in self.steps)

    @property
    def total_cost(self) -> float:
        return sum(self._price(step.stats)[2] for step in self.steps)

    def _price(self, stats: AssignmentStats) -> tuple[float, float, float]:
        input_cost = stats.total_input_tokens * self.cost_per_mil_input / 1_000_000
        output_cost = stats.total_output_tokens * self.cost_per_mil_output / 1_000_000
        return input_cost, output_cost, input_cost + output_cost

    def _build_summary_section(self, elapsed_seconds: float) -> JsonValue:
        return {
            'title': 'Pipeline token usage and cost',
            'headers': [
                'Step',
                'LLM calls',
                'Input tokens',
                'Output tokens',
                'Cost (USD)',
            ],
            'rows': [
                {
                    'step': step.name,
                    'llm_calls': step.stats.total_calls,
                    'input_tokens': step.stats.total_input_tokens,
                    'output_tokens': step.stats.total_output_tokens,
                    'cost_usd': round(self._price(step.stats)[2], 2),
                }
                for step in self.steps
            ],
            'totals': {
                'input_tokens': self.total_input_tokens,
                'output_tokens': self.total_output_tokens,
                'cost_usd': round(self.total_cost, 2),
            },
            'meta': {
                'model_name': self.model_name,
                'cost_per_mil_input': self.cost_per_mil_input,
                'cost_per_mil_output': self.cost_per_mil_output,
                'elapsed_seconds': elapsed_seconds,
            },
        }

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
