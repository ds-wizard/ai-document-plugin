import json
import logging
import pathlib
import time

from ai_document_plugin_service.ai.assignment import AssignmentComponent
from ai_document_plugin_service.ai.assignment.io import save_assignments
from ai_document_plugin_service.ai.common import (
    AssignmentStats,
    configure_logging,
)
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.generation.dmp_generator import (
    generate_dmp_markdown,
)
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import get_questionnaire_detail
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.polishing.dmp_polisher import polish_dmp
from haystack import Pipeline

# Cost per million tokens (USD) - adjust for your model
COST_PER_MIL_INPUT = 0.25
COST_PER_MIL_OUTPUT = 2.0

logger = logging.getLogger(__name__)


def _price(stats: AssignmentStats) -> tuple[float, float, float]:
    input_cost = stats.total_input_tokens * COST_PER_MIL_INPUT / 1_000_000
    output_cost = stats.total_output_tokens * COST_PER_MIL_OUTPUT / 1_000_000
    return input_cost, output_cost, input_cost + output_cost


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


def run_pipeline(questionnaire_uuid: str, token: str) -> None:
    t1 = time.time()
    config = load_config()
    configure_logging(config.log_level)
    model_name = config.model
    file_paths = config.files

    km_data = get_questionnaire_detail(questionnaire_uuid, token)

    with pathlib.Path(file_paths.dmp_template).open(encoding='utf-8') as f:
        template_data = json.load(f)

    replies = km_data['replies']
    km = km_data['knowledgeModel']
    all_stats: list[tuple[str, AssignmentStats]] = []

    pipeline = Pipeline()
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent()
    pipeline.add_component("parser_component", parser_component)
    pipeline.add_component("assignment_component", assignment_component)
    pipeline.connect('parser_component.data', 'assignment_component.data')
    pipeline.run(
        data={
            'parser_component': {'data': km_data},
            'assignment_component': {
                'template_data': template_data,
                'config': config,
                'km': km,
            },
        },
    )

    # # Step 1: Hierarchical assignment (returns assignments)
    # logger.debug('Step 1: Assigning questions to sections...')
    # top_questions = parse_questionnaire(km_data)
    # assignments, stats2 = run_assignment(
    #     template_data,
    #     top_questions,
    #     config,
    #     km,
    # )
    # save_assignments(assignments, file_paths.assignments_output, stats=stats2)
    # all_stats.append(('2. Hierarchical assignment', stats2))
    # logger.debug('Saved assignments to %s', file_paths.assignments_output)
    #
    # # Step 2: DMP generator (returns markdown and debug markdown)
    # logger.debug('Step 2: Generating DMP markdown...')
    # assignments_as_dict = [a.to_dict() for a in assignments]
    # stats3 = AssignmentStats()
    # markdown, debug_markdown, stats3 = generate_dmp_markdown(
    #     assignments_as_dict,
    #     replies,
    #     km,
    #     stats=stats3,
    # )
    # all_stats.append(('2. DMP generator', stats3))
    #
    # # Save pre-polished version before step 4
    # pathlib.Path(file_paths.output_pre_polish_markdown).write_text(
    #     debug_markdown,
    #     encoding='utf-8',
    # )
    # logger.debug(
    #     'Saved pre-polished DMP to %s',
    #     file_paths.output_pre_polish_markdown,
    # )
    #
    # # Step 3: DMP polisher (reorganize content into relevant sections)
    # logger.debug(
    #     'Step 3: Polishing DMP (moving content to relevant sections)...',
    # )
    # stats4 = AssignmentStats()
    # markdown = polish_dmp(
    #     markdown,
    #     config_path=file_paths.config_path,
    #     stats=stats4,
    #     template_data=template_data,
    # )
    # all_stats.append(('4. DMP polisher', stats4))
    #
    # # Build token/cost summary table
    # total_input = sum(s.total_input_tokens for _, s in all_stats)
    # total_output = sum(s.total_output_tokens for _, s in all_stats)
    # total_cost = sum(_price(s)[2] for _, s in all_stats)
    #
    # table_rows = [
    #     [
    #         step_name,
    #         str(stats.total_calls),
    #         str(stats.total_input_tokens),
    #         str(stats.total_output_tokens),
    #         f'{_price(stats)[2]:.2f}',
    #     ]
    #     for step_name, stats in all_stats
    # ]
    # table_rows.append(
    #     [
    #         '**Total**',
    #         '',
    #         str(total_input),
    #         str(total_output),
    #         f'**{total_cost:.2f}**',
    #     ],
    # )
    # table_md = _markdown_table(
    #     ['Step', 'LLM calls', 'Input tokens', 'Output tokens', 'Cost (USD)'],
    #     table_rows,
    # )
    # t2 = time.time()
    #
    # summary_section = '\n'.join(
    #     [
    #         '',
    #         '',
    #         '---',
    #         '',
    #         '## Pipeline token usage and cost',
    #         '',
    #         table_md,
    #         '',
    #         (
    #             f'*Model: {model_name}.'
    #             f'Cost per million tokens: input {COST_PER_MIL_INPUT} USD,'
    #             f'output {COST_PER_MIL_OUTPUT} USD.*'
    #         ),
    #         f'Total time: {t2 - t1}s',
    #     ],
    # )
    # full_markdown = markdown + summary_section
    #
    # pathlib.Path(file_paths.output_markdown).write_text(
    #     full_markdown,
    #     encoding='utf-8',
    # )
    #
    # logger.debug('Saved DMP to %s', file_paths.output_markdown)
    # logger.debug('Token usage and cost:')
    # for step_name, stats in all_stats:
    #     _, _, tot = _price(stats)
    #     logger.debug(
    #         '%s: %s calls, %s in / %s out tokens, %.2f USD',
    #         step_name,
    #         f'{stats.total_calls:,}',
    #         f'{stats.total_input_tokens:,}',
    #         f'{stats.total_output_tokens:,}',
    #         tot,
    #     )
    # logger.debug(
    #     'Total: %s in / %s out tokens, %.2f USD',
    #     f'{total_input:,}',
    #     f'{total_output:,}',
    #     total_cost,
    # )


if __name__ == '__main__':
    config = load_config()
    questionnaire_uuid = config.questionnaire_uuid
    token = config.token

    run_pipeline(questionnaire_uuid, token)
