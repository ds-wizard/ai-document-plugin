import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

from ai_document_plugin_service.ai.common.types import AssignmentStats


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

    def append_summary(self, markdown: str, elapsed_seconds: float) -> str:
        if not self.steps:
            return markdown
        return markdown + self._build_summary_section(elapsed_seconds)

    def write_output(self, markdown: str, output_path: str, elapsed_seconds: float) -> None:
        full_markdown = self.append_summary(markdown, elapsed_seconds)
        pathlib.Path(output_path).write_text(full_markdown, encoding='utf-8')

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

    def _build_summary_section(self, elapsed_seconds: float) -> str:
        table_rows = [
            [
                step.name,
                str(step.stats.total_calls),
                str(step.stats.total_input_tokens),
                str(step.stats.total_output_tokens),
                f'{self._price(step.stats)[2]:.2f}',
            ]
            for step in self.steps
        ]
        table_rows.append(
            [
                '**Total**',
                '',
                str(self.total_input_tokens),
                str(self.total_output_tokens),
                f'**{self.total_cost:.2f}**',
            ],
        )
        table_md = _markdown_table(
            ['Step', 'LLM calls', 'Input tokens', 'Output tokens', 'Cost (USD)'],
            table_rows,
        )

        return '\n'.join(
            [
                '',
                '',
                '---',
                '',
                '## Pipeline token usage and cost',
                '',
                table_md,
                '',
                (
                    f'*Model: {self.model_name}.'
                    f'Cost per million tokens: input {self.cost_per_mil_input} USD,'
                    f'output {self.cost_per_mil_output} USD.*'
                ),
                f'Total time: {elapsed_seconds}s',
            ],
        )


def get_component_output(
    pipeline_result: dict[str, Any],
    component_name: str,
    output_name: str,
) -> Any:
    component_result = pipeline_result.get(component_name)
    if not isinstance(component_result, dict):
        return None
    return component_result.get(output_name)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(row: list[str]) -> str:
        return '| ' + ' | '.join(cell.ljust(widths[index]) for index, cell in enumerate(row)) + ' |'

    separator = '| ' + ' | '.join('-' * width for width in widths) + ' |'
    lines = [format_row(headers), separator]
    lines.extend(format_row(row) for row in rows)
    return '\n'.join(lines)
