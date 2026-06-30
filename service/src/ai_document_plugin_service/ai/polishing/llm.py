from typing import TYPE_CHECKING

from ai_document_plugin_service.ai.common import AssignmentStats, Config
from ai_document_plugin_service.ai.common.llm_client import LLMClient, add_usage, call_with_retry

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )


class SectionPolishingLLM:
    def __init__(self, llm_client: LLMClient, config: Config) -> None:
        self.config = config
        self.client = llm_client

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

        response = await call_with_retry(
            lambda: self.client.completion(
                messages=messages,
                temperature=self.config.dmp_polishing.temperature,
                max_tokens=self.config.dmp_polishing.max_tokens,
            ),
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or '').strip()
