from abc import ABC, abstractmethod
from typing import Optional

from openai import OpenAI

from ai_document_plugin_service.ai.common.config import DEFAULT_CONFIG_PATH, load_config
from ai_document_plugin_service.ai.common.llm_client import call_with_retry, add_usage
from ai_document_plugin_service.ai.common.types import AssignmentStats


class GenerationLLM(ABC):
    @abstractmethod
    def section_from_qa(
            self,
            prompt: str,
            stats: Optional[AssignmentStats] = None,
            previously_generated: str = "",
    ) -> str:
        pass

    @abstractmethod
    def polish_dmp(
            self,
            markdown: str,
            structure_str: str = "",
            stats: Optional[AssignmentStats] = None,
    ) -> str:
        pass


class OpenAIGenerationLLM(GenerationLLM):
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config = load_config(config_path)
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.api_url)

    def section_from_qa(
            self,
            prompt: str,
            stats: Optional[AssignmentStats] = None,
            previously_generated: str = "",
    ) -> str:
        user_content = prompt
        response = call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self.config.dmp_generation.system_message},
                    {"role": "user", "content": user_content},
                ],
                temperature=self.config.dmp_generation.temperature,
                max_tokens=self.config.dmp_generation.max_tokens,
            )
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or "").strip()

    def polish_dmp(
            self,
            markdown: str,
            structure_str: str = "",
            stats: Optional[AssignmentStats] = None,
    ) -> str:
        system_prompt = self.config.dmp_polishing.system_message.replace("{sections}", structure_str)
        user_content = self.config.dmp_polishing.user_message.replace("{markdown}", markdown)

        response = call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=self.config.dmp_polishing.temperature,
                max_tokens=self.config.dmp_polishing.max_tokens,
            )
        )
        add_usage(stats, response)
        return (response.choices[0].message.content or "").strip()
