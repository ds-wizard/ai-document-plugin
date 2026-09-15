"""Translate cover page labels without sending document values to the model."""

import json
import logging
from copy import deepcopy

from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment
from ai_document_plugin_service.ai.common.config import SystemPrompt
from ai_document_plugin_service.ai.common.llm_client import LLMClient, add_usage, call_with_retry
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

logger = logging.getLogger(__name__)


def cover_page_translation_labels(definition: CoverPageDefinition) -> dict[str, str]:
    return {
        definition.metadata.title.id: definition.metadata.title.text,
        **{column.id: column.text for column in definition.metadata.columns},
        **{field.id: field.label for field in definition.metadata.fields},
        definition.history.title.id: definition.history.title.text,
        **{column.id: column.text for column in definition.history.columns},
        **{field.id: field.label for section in definition.assigned_sections for field in section.fields},
    }


def cover_page_section_nodes(
    assignments: list[SerializedSectionAssignment],
    prefix: str = 'section',
) -> list[tuple[str, SerializedSectionAssignment]]:
    nodes = []
    for index, node in enumerate(assignments):
        key = f'{prefix}_{index}'
        nodes.append((key, node))
        nodes.extend(cover_page_section_nodes(node['children'] or [], key))
    return nodes


class CoverPageTranslator:
    def __init__(
        self,
        client: LLMClient,
        language: str,
        prompt: SystemPrompt,
        cover_definition: CoverPageDefinition,
    ) -> None:
        self.client = client
        self.language = language
        self.prompt = prompt
        self.cover_definition = cover_definition

    async def translate(
        self,
        assignments: list[SerializedSectionAssignment],
        stats: AssignmentStats,
    ) -> tuple[dict[str, str], list[SerializedSectionAssignment]]:
        localized = deepcopy(assignments)
        nodes = cover_page_section_nodes(localized)
        labels = {
            **cover_page_translation_labels(self.cover_definition),
            **{key: node['title'] for key, node in nodes},
        }
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
            if (
                isinstance(translated, str)
                and translated.strip()
                and not any(character in translated for character in '\n\r|<>`#*[]')
            ):
                labels[key] = translated.strip()
            else:
                logger.warning(
                    'Missing or invalid cover page label translation; using source label',
                    extra={'label_key': key},
                )
                labels[key] = original
        for key, node in nodes:
            node['title'] = labels[key]
        return labels, localized
