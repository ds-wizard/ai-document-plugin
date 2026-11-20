from typing import TYPE_CHECKING

from ai_document_plugin_service.ai.common import AssignmentStats, Config
from ai_document_plugin_service.ai.common.llm_client import LLMClient, add_usage
from ai_document_plugin_service.ai.common.source_ids import extract_source_ids
from ai_document_plugin_service.ai.common.source_retry import generate_with_valid_sources
from ai_document_plugin_service.data.languages import get_language_name

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )


class SectionPolishingLLM:
    def __init__(self, llm_client: LLMClient, config: Config, language: str) -> None:
        self.config = config
        self.client = llm_client
        self.language = get_language_name(language)

    def get_max_workers(self) -> int:
        return self.client.get_max_workers()

    async def polish_dmp(
        self,
        markdown: str,
        structure_str: str = '',
        stats: AssignmentStats | None = None,
    ) -> str:
        system_prompt = self.config.dmp_polishing.system_message.replace(
            '{sections}',
            structure_str,
        ).replace('{language}', self.language)
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
        allowed_ids = extract_source_ids(markdown)

        async def generate(repair_instruction: str) -> str:
            request_messages = list(messages)
            if repair_instruction:
                request_messages.append({'role': 'user', 'content': repair_instruction})
            response = await self.client.completion(
                stats=stats,
                messages=request_messages,
                temperature=self.config.dmp_polishing.temperature,
                max_completion_tokens=self.config.dmp_polishing.max_tokens,
            )
            add_usage(stats, response)
            return (response.choices[0].message.content or '').strip()

        return await generate_with_valid_sources(generate, allowed_ids, require_sources=bool(allowed_ids))
