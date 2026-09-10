"""Translate header labels without sending document values to the model."""

import json
import logging
from copy import deepcopy

from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment
from ai_document_plugin_service.ai.common.config import SystemPrompt
from ai_document_plugin_service.ai.common.llm_client import LLMClient, add_usage, call_with_retry
from ai_document_plugin_service.ai.common.types import AssignmentStats

logger = logging.getLogger(__name__)

HEADER_LABELS = {
    'document_title': 'Data Management Plan',
    'field': 'Field',
    'value': 'Value',
    'project_name': 'Project Name',
    'based_on': 'Based On',
    'project_phase': 'Project Phase',
    'created_by': 'Created By',
    'generated_on': 'Generated On',
    'history_title': 'History of Changes',
    'version': 'Version',
    'date': 'Date',
    'changes': 'Changes',
    'project_title': 'Project title',
    'project_acronym': 'Project acronym',
    'project_code': 'Project number/code',
    'funding': 'Funding',
    'project_duration': 'Project duration',
    'project_abstract': 'Project abstract',
}


def header_section_nodes(
    assignments: list[SerializedSectionAssignment],
    prefix: str = 'section',
) -> list[tuple[str, SerializedSectionAssignment]]:
    nodes = []
    for index, node in enumerate(assignments):
        key = f'{prefix}_{index}'
        nodes.append((key, node))
        nodes.extend(header_section_nodes(node['children'] or [], key))
    return nodes


class HeaderTranslator:
    def __init__(self, client: LLMClient, language: str, prompt: SystemPrompt) -> None:
        self.client = client
        self.language = language
        self.prompt = prompt

    async def translate(
        self,
        assignments: list[SerializedSectionAssignment],
        stats: AssignmentStats,
    ) -> tuple[dict[str, str], list[SerializedSectionAssignment]]:
        localized = deepcopy(assignments)
        nodes = header_section_nodes(localized)
        labels = {**HEADER_LABELS, **{key: node['title'] for key, node in nodes}}
        if self.language.lower().split('-')[0] == 'en':
            return labels, localized

        response = await call_with_retry(
            lambda: self.client.completion(
                stats=stats,
                messages=[
                    {
                        'role': 'system',
                        'content': self.prompt.system_message.replace('{language}', self.language),
                    },
                    {'role': 'user', 'content': json.dumps(labels, ensure_ascii=False)},
                ],
                temperature=self.prompt.temperature,
                max_tokens=self.prompt.max_tokens,
                reasoning_effort='low',
            ),
        )
        add_usage(stats, response)
        try:
            translations = json.loads(response.choices[0].message.content or '')
        except (ValueError, TypeError):
            translations = {}
        if not isinstance(translations, dict):
            translations = {}
        for key, original in labels.items():
            translated = translations.get(key)
            if isinstance(translated, str) and translated.strip() and not any(
                character in translated for character in '\n\r|<>`#*[]'
            ):
                labels[key] = translated.strip()
            else:
                logger.warning(
                    'Missing or invalid header label translation; using source label', extra={'label_key': key},
                )
                labels[key] = original
        for key, node in nodes:
            node['title'] = labels[key]
        return labels, localized
