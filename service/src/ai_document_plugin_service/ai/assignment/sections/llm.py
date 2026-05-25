import typing
from abc import ABC, abstractmethod

from openai import OpenAI
from tqdm import tqdm

from ai_document_plugin_service.ai.assignment.types import LeafSection
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import (
    add_usage,
    call_with_retry, LLMClient,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats


class SectionIdGenerator(ABC):
    @abstractmethod
    def generate_leaf_section_ids(
        self,
        leaf_sections: list[LeafSection],
        stats: AssignmentStats,
    ) -> dict[str, str]:
        """Return record_id -> sid (short LLM-facing id) for every leaf section.

        The `LeafSection.id` is the dictionary key; the human `title` is used only inside
        the prompt for display.
        """


class OpenAISectionIdGenerator(SectionIdGenerator):
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = LLMClient(config)

    @typing.override
    def generate_leaf_section_ids(
        self,
        leaf_sections: list[LeafSection],
        stats: AssignmentStats,
    ) -> dict[str, str]:
        """Generate one short unique sid per leaf section.

        Returns:
            Mapping of `record_id -> sid`.
        """
        system_msg = self.config.section_id.system_message
        user_tpl = self.config.section_id.user_message
        result: dict[str, str] = {}
        used_ids: set[str] = set()

        for leaf in tqdm(leaf_sections):
            existing_str = ', '.join(sorted(used_ids)) if used_ids else '(none yet)'
            content_block = leaf.text.strip()
            user_msg = (
                user_tpl.replace('{existing_ids}', existing_str)
                .replace('{section_title}', leaf.title)
                .replace('{section_content}', content_block)
            )
            response = call_with_retry(
                lambda um=user_msg: self.client.completion(
                    model=self.config.model,
                    messages=[
                        {'role': 'system', 'content': system_msg},
                        {'role': 'user', 'content': um},
                    ],
                    reasoning_effort='low',
                    temperature=self.config.section_id.temperature,
                    max_tokens=self.config.section_id.max_tokens,
                ),
            )
            add_usage(stats, response)
            choice = response.choices[0]
            raw = (choice.message.content or '').strip().splitlines()[0].strip()
            sid = _normalize_section_id(raw)
            if not sid:
                sid = f's{len(result) + 1}'
            while sid in used_ids:
                sid = f'{sid}_{len(used_ids)}'
            used_ids.add(sid)
            result[leaf.id] = sid

        return result


def _normalize_section_id(raw: str) -> str:
    """Short alphanumeric + hyphen/underscore id, or empty if nothing usable."""
    s = ''.join(c for c in raw if c.isalnum() or c in '-_').strip('-_') or raw[:12]
    return s[:24] if s else ''


class LoggingNoopSectionIdGenerator(SectionIdGenerator):
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.api_url)

    @typing.override
    def generate_leaf_section_ids(  # ty: ignore[invalid-method-override]
        self,
        leaf_sections: list[LeafSection],
        _: AssignmentStats,
    ) -> dict[str, str]:
        res = {}
        for i, leaf in tqdm(enumerate(leaf_sections)):
            res[leaf.id] = f'{leaf.id}_{i}'
        return res
