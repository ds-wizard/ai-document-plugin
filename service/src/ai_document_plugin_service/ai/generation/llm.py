from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import (
    LLMClient,
    add_usage,
)
from ai_document_plugin_service.ai.common.source_retry import generate_with_valid_sources
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.data.languages import get_language_name

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )


class GenerationLLM(ABC):
    @abstractmethod
    def get_max_workers(self) -> int:
        pass

    @abstractmethod
    async def section_from_qa(
        self,
        prompt: str,
        stats: AssignmentStats | None = None,
        previously_generated: str = '',
        *,
        allowed_source_ids: set[str] | None = None,
    ) -> str:
        pass


class SectionGenerationLLM(GenerationLLM):
    def __init__(self, llm_client: LLMClient, config: Config, language: str) -> None:
        self.config = config
        self.client = llm_client
        self.language = get_language_name(language)

    def get_max_workers(self) -> int:
        return self.client.get_max_workers()

    def _section_from_qa_messages(
        self,
        prompt: str,
    ) -> list['ChatCompletionMessageParam']:
        system_message: ChatCompletionSystemMessageParam = {
            'role': 'system',
            'content': self.config.dmp_generation.system_message.replace('{language}', self.language),
        }
        user_message: ChatCompletionUserMessageParam = {
            'role': 'user',
            'content': prompt,
        }
        return [system_message, user_message]

    async def section_from_qa(
        self,
        prompt: str,
        stats: AssignmentStats | None = None,
        previously_generated: str = '',
        *,
        allowed_source_ids: set[str] | None = None,
    ) -> str:
        _ = previously_generated
        messages = self._section_from_qa_messages(prompt)

        async def generate(repair_instruction: str) -> str:
            request_messages = list(messages)
            if repair_instruction:
                request_messages.append({'role': 'user', 'content': repair_instruction})
            response = await self.client.completion(
                stats=stats,
                messages=request_messages,
                temperature=self.config.dmp_generation.temperature,
                max_completion_tokens=self.config.dmp_generation.max_tokens,
            )
            add_usage(stats, response)
            return (response.choices[0].message.content or '').strip()

        return await generate_with_valid_sources(generate, allowed_source_ids or set())
