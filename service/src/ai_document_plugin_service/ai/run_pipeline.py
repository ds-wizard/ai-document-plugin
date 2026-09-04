from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from haystack import AsyncPipeline
from haystack.components.routers import ConditionalRouter

from ai_document_plugin_service.ai.assignment.assignment_component import AssignmentComponent
from ai_document_plugin_service.ai.assignment.projects_section import build_header_assignment_template
from ai_document_plugin_service.ai.common import (
    Config,
    PipelineMetricsCollector,
    get_component_markdown,
    get_component_stats,
)
from ai_document_plugin_service.ai.common.execution_logging import log_timing_event
from ai_document_plugin_service.ai.generation.dmp_generator_component import DmpGeneratorComponent
from ai_document_plugin_service.ai.generation.document_header_component import DocumentHeaderComponent
from ai_document_plugin_service.ai.generation.llm import SectionGenerationLLM
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.persistence.assignment_loader_component import AssignmentLoaderComponent
from ai_document_plugin_service.ai.persistence.assignment_saver_component import (
    AssignmentSaverComponent,
    DBSaver,
    SerializedSectionAssignment,
)
from ai_document_plugin_service.ai.persistence.saver_component import SaverComponent
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent
from ai_document_plugin_service.ai.polishing.llm import SectionPolishingLLM

if TYPE_CHECKING:
    from haystack.components.routers.conditional_router import Route

    from ai_document_plugin_service.ai.common.llm_client import LLMClient
    from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
    from ai_document_plugin_service.ai.persistence.database import Database

# Cost per million tokens (USD) - adjust for your model
COST_PER_MIL_INPUT = 0.25
COST_PER_MIL_OUTPUT = 2.0

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def build_pipeline(
    database: Database,
    saver: DBSaver,
    config: Config,
    llm_client: LLMClient,
    language: str,
) -> AsyncPipeline:
    pipeline = AsyncPipeline()
    loader_component = AssignmentLoaderComponent(database=database)
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent(llm_client, config)
    assignment_saver_component = AssignmentSaverComponent(saver=saver)
    dmp_generator_component = DmpGeneratorComponent(
        SectionGenerationLLM(llm_client, config, language),
        projects_generation_prompt=config.projects_generation,
    )
    dmp_polisher_component = DmpPolisherComponent(SectionPolishingLLM(llm_client, config, language))
    document_header_component = DocumentHeaderComponent()
    saver_component = SaverComponent(database=database)

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
    pipeline.add_component('document_header_component', document_header_component)
    pipeline.add_component('saver_component', saver_component)

    # CONNECTIONS
    # loader_component -> router
    pipeline.connect('loader_component.assignments', 'router.assignments')
    pipeline.connect('loader_component.found', 'router.found')
    pipeline.connect('loader_component.header_assignments', 'dmp_generator_component.db_header_assignments')
    # no assignments saved -> continue to parser_component
    pipeline.connect('router.missing_assignment', 'parser_component.trigger')
    # assignments already done -> continue to dmp_generator_component
    pipeline.connect('router.retrieved_assignment', 'dmp_generator_component.db_assignments')
    # parser_component -> assignment_component
    pipeline.connect('parser_component.data', 'assignment_component.data')
    # assignment_component -> assignment_saver_component
    pipeline.connect('assignment_component.assignments', 'assignment_saver_component.assignments')
    pipeline.connect('assignment_component.header_assignments', 'assignment_saver_component.header_assignments')
    pipeline.connect('assignment_component.stats', 'assignment_saver_component.stats')
    # assignment_saver_component -> dmp_generator_component
    pipeline.connect('assignment_saver_component.assignments', 'dmp_generator_component.new_assignments')
    pipeline.connect('assignment_saver_component.header_assignments', 'dmp_generator_component.new_header_assignments')
    # dmp_generator_component -> prepolished_saver_component
    pipeline.connect('dmp_generator_component.debug_markdown', 'saver_component.debug_markdown')
    # dmp_generator_component -> dmp_polisher_component
    pipeline.connect('dmp_generator_component.markdown', 'dmp_polisher_component.markdown')
    # Add fixed metadata only after the LLM has polished the document body.
    pipeline.connect('dmp_generator_component.document_header', 'document_header_component.document_header')
    pipeline.connect('dmp_polisher_component.markdown', 'document_header_component.markdown')
    pipeline.connect('document_header_component.markdown', 'saver_component.markdown')

    return pipeline


async def run_pipeline(
    questionnaire_uuid: UUID,
    template_uuid: UUID,
    template_title: str,
    template_data: Mapping[str, object],
    user_uuid: UUID,
    tenant_uuid: UUID,
    pipeline: AsyncPipeline,
    database: Database,
    dsw_client: DSWClient,
    model_name: str,
    *,
    generate_dmp_metadata: bool = False,
    on_progress: ProgressCallback | None = None,
) -> tuple[UUID, str]:
    t1 = time.time()
    pipeline_total_started = time.perf_counter()
    questionnaire_fetch_started = time.perf_counter()
    try:
        km_data = await dsw_client.get_questionnaire_detail(questionnaire_uuid=questionnaire_uuid)
    except Exception:
        logger.exception('Failed to load questionnaire detail', extra={'questionnaire_uuid': str(questionnaire_uuid)})
        raise
    log_timing_event(
        'questionnaire_detail_loaded',
        duration_ms=round((time.perf_counter() - questionnaire_fetch_started) * 1000, 3),
    )
    project_versions: list[dict] = []
    if generate_dmp_metadata:
        project_versions_fetch_started = time.perf_counter()
        try:
            project_versions = await dsw_client.get_project_versions(project_uuid=questionnaire_uuid)
        except Exception:
            logger.exception('Failed to load project versions', extra={'questionnaire_uuid': str(questionnaire_uuid)})
            raise
        log_timing_event(
            'project_versions_loaded',
            duration_ms=round((time.perf_counter() - project_versions_fetch_started) * 1000, 3),
        )

    replies = km_data['replies']
    km = km_data['knowledgeModel']
    header_assignment_template = build_header_assignment_template() if generate_dmp_metadata else None
    knowledge_model_uuid = UUID(km_data['knowledgeModelPackage']['uuid'])
    knowledge_model_name = km_data['knowledgeModelPackage']['name']
    knowledge_model_version = km_data['knowledgeModelPackage']['version']

    if on_progress is not None:
        on_progress('Preparing document template')

    pipeline_started = time.perf_counter()
    try:
        result = await pipeline.run_async(
            data={
                'loader_component': {
                    'knowledge_model_uuid': knowledge_model_uuid,
                    'template_uuid': template_uuid,
                    'include_header_assignments': generate_dmp_metadata,
                },
                'parser_component': {'data': km_data},
                'assignment_component': {
                    'template_data': dict(template_data),
                    'header_template_data': header_assignment_template,
                    'km': km,
                    'on_progress': on_progress,
                },
                'assignment_saver_component': {
                    'knowledge_model_uuid': knowledge_model_uuid,
                    'knowledge_model_name': knowledge_model_name,
                    'knowledge_model_version': knowledge_model_version,
                    'template_uuid': template_uuid,
                    'template_title': template_title,
                    'template_data': template_data,
                    'tenant_uuid': tenant_uuid,
                },
                'dmp_generator_component': {
                    'replies': replies,
                    'km': km,
                    'questionnaire_detail': km_data,
                    'project_versions': project_versions,
                    'generate_dmp_metadata': generate_dmp_metadata,
                    'on_progress': on_progress,
                },
                'dmp_polisher_component': {
                    'template_data': template_data,
                    'on_progress': on_progress,
                },
                'saver_component': {
                    'template_uuid': template_uuid,
                    'knowledge_model_uuid': knowledge_model_uuid,
                    'user_uuid': user_uuid,
                    'tenant_uuid': tenant_uuid,
                },
            },
            include_outputs_from={
                'assignment_saver_component',
                'dmp_generator_component',
                'dmp_polisher_component',
                'saver_component',
            },
        )
    except Exception:
        logger.exception(
            'Pipeline component execution failed',
            extra={'questionnaire_uuid': str(questionnaire_uuid), 'template_uuid': str(template_uuid)},
        )
        raise
    log_timing_event(
        'pipeline_components_finished',
        duration_ms=round((time.perf_counter() - pipeline_started) * 1000, 3),
    )

    result_markdown = get_component_markdown(result, 'saver_component')
    if result_markdown is None:
        msg = 'Missing markdown output from saver_component'
        logger.error(msg, extra={'template_uuid': str(template_uuid)})
        raise RuntimeError(msg)

    assignment_stats = get_component_stats(result, 'assignment_saver_component')
    generation_stats = get_component_stats(result, 'dmp_generator_component')
    polishing_stats = get_component_stats(result, 'dmp_polisher_component')

    metrics_started = time.perf_counter()
    try:
        await write_metrics(
            database,
            template_uuid,
            knowledge_model_uuid,
            user_uuid,
            tenant_uuid,
            result,
            model_name,
            t1,
        )
    except Exception:
        logger.exception(
            'Failed to persist pipeline metrics',
            extra={'template_uuid': str(template_uuid), 'knowledge_model_uuid': str(knowledge_model_uuid)},
        )
        raise
    log_timing_event(
        'pipeline_metrics_saved',
        duration_ms=round((time.perf_counter() - metrics_started) * 1000, 3),
    )
    log_timing_event(
        'pipeline_summary',
        generation_ms=generation_stats.total_duration_ms if generation_stats is not None else None,
        polishing_ms=polishing_stats.total_duration_ms if polishing_stats is not None else None,
        total_pipeline_ms=round((time.perf_counter() - pipeline_total_started) * 1000, 3),
        total_llm_wait_ms=round(
            sum(
                stats.total_llm_wait_ms
                for stats in (assignment_stats, generation_stats, polishing_stats)
                if stats is not None
            ),
            3,
        ),
        total_llm_response_ms=round(
            sum(
                stats.total_llm_response_ms
                for stats in (assignment_stats, generation_stats, polishing_stats)
                if stats is not None
            ),
            3,
        ),
    )
    return knowledge_model_uuid, result_markdown


async def write_metrics(
    database: Database,
    template_uuid: UUID,
    knowledge_model_uuid: UUID,
    user_uuid: UUID,
    tenant_uuid: UUID,
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
    await database.save_stats(
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
