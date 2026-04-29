import json
import logging
import pathlib
import time
from collections.abc import Mapping

from haystack import Pipeline
from haystack.components.routers import ConditionalRouter

from ai_document_plugin_service.ai.assignment import AssignmentComponent
from ai_document_plugin_service.ai.common import (
    PipelineMetricsCollector,
    configure_logging,
    get_component_markdown,
    get_component_stats,
)
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.generation.dmp_generator_component import DmpGeneratorComponent
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import get_questionnaire_detail
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.persistence.assignment_loader_component import AssignmentLoaderComponent
from ai_document_plugin_service.ai.persistence.assignment_saver_component import (
    AssignmentSaverComponent,
    DBSaver,
    JsonValue,
)
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.ai.persistence.saver_component import SaverComponent
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent

# Cost per million tokens (USD) - adjust for your model
COST_PER_MIL_INPUT = 0.25
COST_PER_MIL_OUTPUT = 2.0

logger = logging.getLogger(__name__)


def build_pipeline() -> Pipeline:
    pipeline = Pipeline()
    loader_component = AssignmentLoaderComponent()
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent()
    assignment_saver_component = AssignmentSaverComponent()
    dmp_generator_component = DmpGeneratorComponent()
    prepolished_saver_component = SaverComponent()
    dmp_polisher_component = DmpPolisherComponent()
    polished_saver_component = SaverComponent()

    # ROUTES
    routes = [
        {
            'condition': '{{ not found }}',
            'output': '{{ found }}',
            'output_name': 'missing_assignment',
            'output_type': bool,
        },
        {
            'condition': '{{ found }}',
            'output': '{{ assignments }}',
            'output_name': 'retrieved_assignment',
            'output_type': JsonValue,
        },
    ]
    router = ConditionalRouter(routes=routes)

    # COMPONENTS
    pipeline.add_component('loader_component', loader_component)
    pipeline.add_component('router', router)
    pipeline.add_component('parser_component', parser_component)
    pipeline.add_component('assignment_component', assignment_component)
    pipeline.add_component('assignment_saver_component', assignment_saver_component)
    pipeline.add_component('dmp_generator_component', dmp_generator_component)
    pipeline.add_component('prepolished_saver_component', prepolished_saver_component)
    pipeline.add_component('dmp_polisher_component', dmp_polisher_component)
    pipeline.add_component('polished_saver_component', polished_saver_component)

    # CONNECTIONS
    # loader_component -> router
    pipeline.connect('loader_component.assignments', 'router.assignments')
    pipeline.connect('loader_component.found', 'router.found')
    # no assignments saved -> continue to parser_component
    pipeline.connect('router.missing_assignment', 'parser_component.trigger')
    # assignments already done -> continue to dmp_generator_component
    pipeline.connect('router.retrieved_assignment', 'dmp_generator_component.db_assignments')
    # parser_component -> assignment_component
    pipeline.connect('parser_component.data', 'assignment_component.data')
    # assignment_component -> assignment_saver_component
    pipeline.connect('assignment_component.assignments', 'assignment_saver_component.assignments')
    pipeline.connect('assignment_component.stats', 'assignment_saver_component.stats')
    # assignment_saver_component -> dmp_generator_component
    pipeline.connect('assignment_saver_component.assignments', 'dmp_generator_component.new_assignments')
    # dmp_generator_component -> prepolished_saver_component
    pipeline.connect('dmp_generator_component.debug_markdown', 'prepolished_saver_component.debug_markdown')
    pipeline.connect('dmp_generator_component.markdown', 'prepolished_saver_component.markdown')
    # prepolisher_saver_component -> dmp_polisher_component
    pipeline.connect('prepolished_saver_component.markdown', 'dmp_polisher_component.markdown')
    # dmp_polisher_component -> polished_saver_component
    pipeline.connect('dmp_polisher_component.markdown', 'polished_saver_component.debug_markdown')
    pipeline.connect('dmp_polisher_component.markdown', 'polished_saver_component.markdown')

    return pipeline


def run_pipeline(
    questionnaire_uuid: str, token: str, template_uuid: str, template_title: str, pipeline: Pipeline
) -> None:
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
    knowledge_model_uuid = km_data['knowledgeModelPackage']['uuid']
    knowledge_model_name = km_data['knowledgeModelPackage']['name']
    knowledge_model_version = km_data['knowledgeModelPackage']['version']
    database = PostgresDB(config.database)
    saver = DBSaver(database)

    # OTHER INPUTS
    result = pipeline.run(
        data={
            'loader_component': {
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': template_uuid,
                'database': database,
            },
            'parser_component': {'data': km_data},
            'assignment_component': {
                'template_data': template_data,
                'config': config,
                'km': km,
            },
            'assignment_saver_component': {
                'saver': saver,
                'knowledge_model_uuid': knowledge_model_uuid,
                'knowledge_model_name': knowledge_model_name,
                'knowledge_model_version': knowledge_model_version,
                'template_uuid': template_uuid,
                'template_title': template_title,
                'template_data': template_data,
            },
            'dmp_generator_component': {
                'replies': replies,
                'km': km,
                'workers': config.parallel_workers,
            },
            'prepolished_saver_component': {'file_path': file_paths.output_pre_polish_markdown},
            'dmp_polisher_component': {
                'config_path': file_paths.config_path,
                'template_data': template_data,
            },
            'polished_saver_component': {'file_path': file_paths.output_markdown},
        },
        include_outputs_from={
            'assignment_saver_component',
            'dmp_generator_component',
            'dmp_polisher_component',
            'polished_saver_component',
        },
    )

    write_metrics(result, model_name, file_paths.output_markdown, file_paths.output_with_stats, t1)


def write_metrics(
    result: Mapping[str, object],
    model_name: str,
    output_path: str,
    output_with_stats_path: str,
    t1: float,
) -> None:
    metrics = PipelineMetricsCollector(
        model_name=model_name,
        cost_per_mil_input=COST_PER_MIL_INPUT,
        cost_per_mil_output=COST_PER_MIL_OUTPUT,
    )
    metrics.add_step(
        '1. Hierarchical assignment',
        get_component_stats(result, 'assignment_saver_component'),
    )
    metrics.add_step(
        '2. DMP generator',
        get_component_stats(result, 'dmp_generator_component'),
    )
    metrics.add_step(
        '3. DMP polisher',
        get_component_stats(result, 'dmp_polisher_component'),
    )

    polished_markdown = get_component_markdown(result, 'polished_saver_component')
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
    template_uuid = config.template_uuid
    template_title = config.template_title

    pipeline = build_pipeline()
    run_pipeline(
        questionnaire_uuid,
        token,
        template_uuid,
        template_title,
        pipeline,
    )
