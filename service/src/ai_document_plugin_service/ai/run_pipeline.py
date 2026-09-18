from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from haystack import AsyncPipeline
from haystack.components.routers import ConditionalRouter

from ai_document_plugin_service.ai.assignment.assignment_component import AssignmentComponent
from ai_document_plugin_service.ai.common import (
    Config,
    PipelineMetricsCollector,
    PipelineStats,
    StepUsage,
    get_component_markdown,
    get_component_stats,
)
from ai_document_plugin_service.ai.common.execution_logging import log_timing_event
from ai_document_plugin_service.ai.generation.dmp_generator_component import DmpGeneratorComponent
from ai_document_plugin_service.ai.generation.llm import SectionGenerationLLM
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.ai.persistence.assignment_loader_component import AssignmentLoaderComponent
from ai_document_plugin_service.ai.persistence.assignment_saver_component import (
    AssignmentSaverComponent,
    DBSaver,
    SerializedSectionAssignment,
)
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent
from ai_document_plugin_service.ai.polishing.llm import SectionPolishingLLM

if TYPE_CHECKING:
    from haystack.components.routers.conditional_router import Route

    from ai_document_plugin_service.ai.common.llm_client import LLMClient
    from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
    from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class PipelineOutput:
    knowledge_model_uuid: UUID
    markdown: str
    # Generator output before polishing (the text fed into the polisher).
    dmp_pre_polished: str
    stats: PipelineStats


def build_pipeline(
    database: Database, saver: DBSaver, config: Config, llm_client: LLMClient, language: str
) -> AsyncPipeline:
    pipeline = AsyncPipeline()
    loader_component = AssignmentLoaderComponent(database=database)
    parser_component = ParserComponent()
    assignment_component = AssignmentComponent(llm_client, config)
    assignment_saver_component = AssignmentSaverComponent(saver=saver)
    dmp_generator_component = DmpGeneratorComponent(SectionGenerationLLM(llm_client, config, language))
    dmp_polisher_component = DmpPolisherComponent(SectionPolishingLLM(llm_client, config, language))

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
    # dmp_generator_component -> dmp_polisher_component
    pipeline.connect('dmp_generator_component.markdown', 'dmp_polisher_component.markdown')

    return pipeline


async def run_pipeline(
    questionnaire_uuid: UUID,
    template_uuid: UUID,
    template_title: str,
    template_data: Mapping[str, object],
    tenant_uuid: UUID,
    pipeline: AsyncPipeline,
    dsw_client: DSWClient,
    on_progress: ProgressCallback | None = None,
) -> PipelineOutput:
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

    replies = km_data['replies']
    km = km_data['knowledgeModel']
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
                },
                'parser_component': {'data': km_data},
                'assignment_component': {
                    'template_data': template_data,
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
                    'on_progress': on_progress,
                },
                'dmp_polisher_component': {
                    'template_data': template_data,
                    'on_progress': on_progress,
                },
            },
            include_outputs_from={
                'assignment_saver_component',
                'dmp_generator_component',
                'dmp_polisher_component',
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
    total_time = time.perf_counter() - pipeline_total_started

    result_markdown = get_component_markdown(result, 'dmp_polisher_component')
    if result_markdown is None:
        msg = 'Missing markdown output from dmp_polisher_component'
        logger.error(msg, extra={'template_uuid': str(template_uuid)})
        raise RuntimeError(msg)

    # The clean generator output, not its debug_markdown (which embeds the source-question tables).
    dmp_pre_polished = get_component_markdown(result, 'dmp_generator_component')
    if dmp_pre_polished is None:
        msg = 'Missing markdown output from dmp_generator_component'
        logger.error(msg, extra={'template_uuid': str(template_uuid)})
        raise RuntimeError(msg)

    assignment_stats = get_component_stats(result, 'assignment_saver_component')
    generation_stats = get_component_stats(result, 'dmp_generator_component')
    polishing_stats = get_component_stats(result, 'dmp_polisher_component')

    pipeline_stats = collect_stats(result, total_time)
    log_timing_event(
        'pipeline_summary',
        generation_ms=generation_stats.total_duration_ms if generation_stats is not None else None,
        polishing_ms=polishing_stats.total_duration_ms if polishing_stats is not None else None,
        total_pipeline_ms=round(total_time * 1000, 3),
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
    return PipelineOutput(
        knowledge_model_uuid=knowledge_model_uuid,
        markdown=result_markdown,
        dmp_pre_polished=dmp_pre_polished,
        stats=pipeline_stats,
    )


def collect_stats(result: Mapping[str, object], total_time: float) -> PipelineStats:
    """Collect per-step LLM usage. Pure, so it can never fail a finished run."""
    assignment_stats = get_component_stats(result, 'assignment_saver_component')
    generation_stats = get_component_stats(result, 'dmp_generator_component')
    polishing_stats = get_component_stats(result, 'dmp_polisher_component')

    metrics = PipelineMetricsCollector()
    metrics.add_step('1. Hierarchical assignment', assignment_stats)
    metrics.add_step('2. DMP generator', generation_stats)
    metrics.add_step('3. DMP polisher', polishing_stats)
    metrics.log_summary(logger)

    return PipelineStats(
        assignment=StepUsage.from_stats(assignment_stats),
        generation=StepUsage.from_stats(generation_stats),
        polishing=StepUsage.from_stats(polishing_stats),
        elapsed_seconds=total_time,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the AI document pipeline from the command line.',
    )
    parser.add_argument('--questionnaire-uuid', required=True, type=UUID, help='DSW questionnaire UUID to process.')
    parser.add_argument('--token', required=True, help='DSW bearer token used to fetch the questionnaire.')
    parser.add_argument('--template-uuid', required=True, type=UUID, help='Template UUID stored in the database.')
    return parser.parse_args()
