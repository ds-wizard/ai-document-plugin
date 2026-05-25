from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ai_document_plugin_service.ai.common.config import (
    Config,
)
from ai_document_plugin_service.ai.common.llm_client import (
    LLMClient,
    add_usage,
    call_with_retry,
    LLMClient,
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
    def section_from_qa(
        self,
        prompt: str,
        stats: AssignmentStats | None = None,
        previously_generated: str = '',
    ) -> str:
        pass

    @abstractmethod
    def polish_dmp(
        self,
        markdown: str,
        structure_str: str = '',
        stats: AssignmentStats | None = None,
    ) -> str:
        pass


class OpenAIGenerationLLM(GenerationLLM):
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = LLMClient(config)

    def section_from_qa(
        self,
        prompt: str,
        stats: AssignmentStats | None = None,
        previously_generated: str = '',
    ) -> str:
        _ = previously_generated
        user_content = prompt
        system_message: ChatCompletionSystemMessageParam = {
            'role': 'system',
            'content': self.config.dmp_generation.system_message,
        }
        user_message: ChatCompletionUserMessageParam = {
            'role': 'user',
            'content': user_content,
        }
        messages: list[ChatCompletionMessageParam] = [
            system_message,
            user_message,
        ]
        response = call_with_retry(
            lambda: self.client.completion(
                model=self.config.model,
                messages=messages,
                temperature=self.config.dmp_generation.temperature,
                max_tokens=self.config.dmp_generation.max_tokens,
            ),
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or '').strip()

    def polish_dmp(
        self,
        markdown: str,
        structure_str: str = '',
        stats: AssignmentStats | None = None,
    ) -> str:
        system_prompt = self.config.dmp_polishing.system_message.replace(
            '{sections}',
            structure_str,
        )
        user_content = self.config.dmp_polishing.user_message.replace(
            '{markdown}',
            markdown,
        )
        system_message: ChatCompletionSystemMessageParam = {
            'role': 'system',
            'content': system_prompt,
        }
        user_message: ChatCompletionUserMessageParam = {
            'role': 'user',
            'content': user_content,
        }
        messages: list[ChatCompletionMessageParam] = [
            system_message,
            user_message,
        ]

        response = call_with_retry(
            lambda: self.client.completion(
                model=self.config.model,
                messages=messages,
                temperature=self.config.dmp_polishing.temperature,
                max_tokens=self.config.dmp_polishing.max_tokens,
            ),
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or '').strip()
