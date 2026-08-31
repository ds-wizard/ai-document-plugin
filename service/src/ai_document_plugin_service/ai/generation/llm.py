from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import (
    LLMClient,
    add_usage,
    call_with_retry,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats

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
    ) -> str:
        pass


class SectionGenerationLLM(GenerationLLM):
    def __init__(self, llm_client: LLMClient, config: Config) -> None:
        self.config = config
        self.client = llm_client

    def get_max_workers(self) -> int:
        return self.client.get_max_workers()

    def _section_from_qa_messages(
        self,
        prompt: str,
    ) -> list['ChatCompletionMessageParam']:
        system_message: ChatCompletionSystemMessageParam = {
            'role': 'system',
            'content': self.config.dmp_generation.system_message,
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
    ) -> str:
        _ = previously_generated
        messages = self._section_from_qa_messages(prompt)
        response = await call_with_retry(
            lambda: self.client.completion(
                stats=stats,
                messages=messages,
                temperature=self.config.dmp_generation.temperature,
                max_tokens=self.config.dmp_generation.max_tokens,
            ),
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or '').strip()
