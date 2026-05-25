from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from haystack import Pipeline
from haystack.components.routers import ConditionalRouter

from ai_document_plugin_service.ai.assignment.assignment_component import AssignmentComponent
from ai_document_plugin_service.ai.common import (
    PipelineMetricsCollector,
    configure_logging,
    get_component_markdown,
    get_component_stats,
)
from ai_document_plugin_service.ai.common.config import (
    LLMConfigOverride,
    apply_llm_override,
    load_config,
)
from ai_document_plugin_service.ai.generation.dmp_generator_component import DmpGeneratorComponent
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import get_questionnaire_detail
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.persistence.assignment_loader_component import AssignmentLoaderComponent
from ai_document_plugin_service.ai.persistence.assignment_saver_component import (
    AssignmentSaverComponent,
    DBSaver,
    SerializedSectionAssignment,
)
from ai_document_plugin_service.ai.persistence.database import Database, PostgresDB
from ai_document_plugin_service.ai.persistence.saver_component import SaverComponent
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from haystack.components.routers.conditional_router import Route

# Cost per million tokens (USD) - adjust for your model
COST_PER_MIL_INPUT = 0.25
COST_PER_MIL_OUTPUT = 2.0

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def build_pipeline() -> Pipeline:
    pipeline = Pipeline()
    loader_component = AssignmentLoaderComponent()
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent()
    assignment_saver_component = AssignmentSaverComponent()
    dmp_generator_component = DmpGeneratorComponent()
    dmp_polisher_component = DmpPolisherComponent()
    saver_component = SaverComponent()

    # ROUTES
    routes: list[Route] = [
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
            'output_type': list[SerializedSectionAssignment],
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
    pipeline.add_component('dmp_polisher_component', dmp_polisher_component)
    pipeline.add_component('saver_component', saver_component)

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
    pipeline.connect('dmp_generator_component.debug_markdown', 'saver_component.debug_markdown')
    # prepolisher_saver_component -> dmp_polisher_component
    pipeline.connect('dmp_generator_component.markdown', 'dmp_polisher_component.markdown')
    # dmp_polisher_component -> polished_saver_component
    pipeline.connect('dmp_polisher_component.markdown', 'saver_component.markdown')

    return pipeline


def run_pipeline(
    questionnaire_uuid: str,
    token: str,
    dsw_api_url: str | None,
    template_uuid: str,
    template_title: str,
    template_data: Mapping[str, object],
    user_uuid: str,
    tenant_uuid: str,
    pipeline: Pipeline,
    llm_override: LLMConfigOverride | None = None,
    on_progress: ProgressCallback | None = None,
) -> tuple[str, str]:
    t1 = time.time()
    config = apply_llm_override(load_config(), llm_override)
    configure_logging(config.log_level)
    model_name = config.model

    km_data = get_questionnaire_detail(questionnaire_uuid, token, dsw_api_url)

    replies = km_data['replies']
    km = km_data['knowledgeModel']
    knowledge_model_uuid = km_data['knowledgeModelPackage']['uuid']
    knowledge_model_name = km_data['knowledgeModelPackage']['name']
    knowledge_model_version = km_data['knowledgeModelPackage']['version']
    database = PostgresDB(config.database)
    saver = DBSaver(database)

    if on_progress is not None:
        on_progress('Preparing document template, initiating.')

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
                'on_progress': on_progress,
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
                'config': config,
                'on_progress': on_progress,
            },
            'dmp_polisher_component': {
                'config': config,
                'template_data': template_data,
                'on_progress': on_progress,
            },
            'saver_component': {
                'template_uuid': template_uuid,
                'knowledge_model_uuid': knowledge_model_uuid,
                'user_uuid': user_uuid,
                'tenant_uuid': tenant_uuid,
                'database': database,
            },
        },
        include_outputs_from={
            'assignment_saver_component',
            'dmp_generator_component',
            'dmp_polisher_component',
            'saver_component',
        },
    )

    result_markdown = get_component_markdown(result, 'saver_component')
    if result_markdown is None:
        msg = 'Missing markdown output from saver_component'
        raise RuntimeError(msg)

    write_metrics(
        database,
        template_uuid,
        knowledge_model_uuid,
        user_uuid,
        tenant_uuid,
        result,
        model_name,
        t1,
    )
    return knowledge_model_uuid, result_markdown


def write_metrics(
    database: Database,
    template_uuid: str,
    knowledge_model_uuid: str,
    user_uuid: str,
    tenant_uuid: str,
    result: Mapping[str, object],
    model_name: str,
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

    t2 = time.time()

    stats = metrics.get_stats(elapsed_seconds=t2 - t1)
    database.save_stats(
        template_uuid=template_uuid,
        knowledge_model_uuid=knowledge_model_uuid,
        user_uuid=user_uuid,
        tenant_uuid=tenant_uuid,
        stats=stats,
    )

    logger.debug('Saved DMP stats')
    metrics.log_summary(logger)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the AI document pipeline from the command line.',
    )
    parser.add_argument('--questionnaire-uuid', required=True, help='DSW questionnaire UUID to process.')
    parser.add_argument('--token', required=True, help='DSW bearer token used to fetch the questionnaire.')
    parser.add_argument('--template-uuid', required=True, help='Template UUID stored in the database.')
    return parser.parse_args()
