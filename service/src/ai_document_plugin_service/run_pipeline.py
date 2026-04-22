import json
import logging
import pathlib
import time

from ai_document_plugin_service.ai.assignment import AssignmentComponent
from ai_document_plugin_service.ai.assignment.assignment_saver_component import AssignmentSaverComponent
from ai_document_plugin_service.ai.common import (
    PipelineMetricsCollector,
    configure_logging,
    get_component_output,
)
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.generation.dmp_generator_component import DmpGeneratorComponent
from ai_document_plugin_service.ai.generation.file_saver_component import FileSaverComponent
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import get_questionnaire_detail
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent
from haystack import Pipeline

# Cost per million tokens (USD) - adjust for your model
COST_PER_MIL_INPUT = 0.25
COST_PER_MIL_OUTPUT = 2.0

logger = logging.getLogger(__name__)

def build_pipeline() -> Pipeline:
    pipeline = Pipeline()
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent()
    assignment_saver_component = AssignmentSaverComponent()
    dmp_generator_component = DmpGeneratorComponent()
    prepolished_saver_component = FileSaverComponent()
    dmp_polisher_component = DmpPolisherComponent()
    polished_saver_component = FileSaverComponent()

    # COMPONENTS
    pipeline.add_component("parser_component", parser_component)
    pipeline.add_component("assignment_component", assignment_component)
    pipeline.add_component("assignment_saver_component", assignment_saver_component)
    pipeline.add_component("dmp_generator_component", dmp_generator_component)
    pipeline.add_component("prepolished_saver_component", prepolished_saver_component)
    pipeline.add_component("dmp_polisher_component", dmp_polisher_component)
    pipeline.add_component("polished_saver_component", polished_saver_component)

    # CONNECTIONS
    # parser_component -> assignment_component
    pipeline.connect('parser_component.data', 'assignment_component.data')
    # assignment_component -> assignment_saver_component
    pipeline.connect('assignment_component.assignments', 'assignment_saver_component.assignments')
    pipeline.connect('assignment_component.stats', 'assignment_saver_component.stats')
    # assignment_saver_component -> dmp_generator_component
    pipeline.connect('assignment_saver_component.assignments', 'dmp_generator_component.assignments')
    # dmp_generator_component -> prepolished_saver_component
    pipeline.connect('dmp_generator_component.debug_markdown', 'prepolished_saver_component.debug_markdown')
    pipeline.connect('dmp_generator_component.markdown', 'prepolished_saver_component.markdown')
    # prepolisher_saver_component -> dmp_polisher_component
    pipeline.connect('prepolished_saver_component.markdown', 'dmp_polisher_component.markdown')
    # dmp_polisher_component -> polished_saver_component
    pipeline.connect('dmp_polisher_component.markdown', 'polished_saver_component.debug_markdown')
    pipeline.connect('dmp_polisher_component.markdown', 'polished_saver_component.markdown')

    return pipeline


def run_pipeline(questionnaire_uuid: str, token: str, pipeline: Pipeline) -> None:
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

    # OTHER INPUTS
    result = pipeline.run(
        data={
            'parser_component': {'data': km_data},
            'assignment_component': {
                'template_data': template_data,
                'config': config,
                'km': km,
            },
            'assignment_saver_component': {
                'output_path': file_paths.assignments_output
            },
            'dmp_generator_component': {
                'replies': replies,
                'km': km,
            },
            'prepolished_saver_component': {
                'file_path': file_paths.output_pre_polish_markdown
            },
            'dmp_polisher_component': {
                'config_path': file_paths.config_path,
                'template_data': template_data,
            },
            'polished_saver_component': {
                'file_path': file_paths.output_markdown
            }
        },
        include_outputs_from={
            'assignment_saver_component',
            'dmp_generator_component',
            'dmp_polisher_component',
            'polished_saver_component',
        },
    )

    write_metrics(result, model_name, file_paths.output_markdown, file_paths.output_with_stats, t1)


def write_metrics(result, model_name, output_path, output_with_stats_path, t1):
    metrics = PipelineMetricsCollector(
        model_name=model_name,
        cost_per_mil_input=COST_PER_MIL_INPUT,
        cost_per_mil_output=COST_PER_MIL_OUTPUT,
    )
    metrics.add_step(
        '1. Hierarchical assignment',
        get_component_output(result, 'assignment_saver_component', 'stats'),
    )
    metrics.add_step(
        '2. DMP generator',
        get_component_output(result, 'dmp_generator_component', 'stats'),
    )
    metrics.add_step(
        '3. DMP polisher',
        get_component_output(result, 'dmp_polisher_component', 'stats'),
    )

    polished_markdown = get_component_output(result, 'polished_saver_component', 'markdown')
    if polished_markdown is None:
        polished_markdown = pathlib.Path(output_path).read_text(
            encoding='utf-8',
        )

    t2 = time.time()
    metrics.write_output(
        markdown=polished_markdown,
        output_path=output_with_stats_path,
        elapsed_seconds=t2 - t1,
    )

    logger.debug('Saved DMP to %s', output_with_stats_path)
    metrics.log_summary(logger)


if __name__ == '__main__':
    config = load_config()
    questionnaire_uuid = config.questionnaire_uuid
    token = config.token

    pipeline = build_pipeline()
    run_pipeline(questionnaire_uuid, token, pipeline)
