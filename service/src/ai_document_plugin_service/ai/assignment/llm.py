import json
import logging
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import TYPE_CHECKING

from json_repair import repair_json

from ai_document_plugin_service.ai.common import AssignmentStats
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import (
    LLMClient,
    add_usage,
    call_with_retry,
)

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionUserMessageParam,
    )

logger = logging.getLogger(__name__)


class ModelDidNotStopError(RuntimeError):
    """Raised when LLM generation does not finish with stop reason."""


class UnableToParseResponseError(ValueError):
    """Raised when LLM response cannot be parsed as expected JSON."""


class LayerMatcher(ABC):
    @abstractmethod
    async def match_questions_to_sections(
        self,
        sections_xml: str,
        question_chunk_xml: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        """Return question_id -> list[section_id]."""


class OpenAILayerMatcher(LayerMatcher):
    def __init__(self, llm_client: LLMClient, config: Config) -> None:
        self.client = llm_client
        self.config = config

    def _assignment_messages(
        self,
        sections_xml: str,
        question_chunk_xml: str,
    ) -> list['ChatCompletionMessageParam']:
        user_message = self.config.assignment.user_message.replace(
            '{question_text}',
            question_chunk_xml,
        ).replace('{sections_list}', sections_xml)
        system_message: ChatCompletionSystemMessageParam = {
            'role': 'system',
            'content': self.config.assignment.system_message,
        }
        user_prompt: ChatCompletionUserMessageParam = {
            'role': 'user',
            'content': user_message,
        }
        return [system_message, user_prompt]

    async def match_questions_to_sections(
        self,
        sections_xml: str,
        question_chunk_xml: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        messages = self._assignment_messages(sections_xml, question_chunk_xml)

        async def call_and_parse() -> dict[str, list[str]]:
            response = await self.client.completion(
                messages=messages,
                temperature=self.config.assignment.temperature,
                max_tokens=self.config.assignment.max_tokens,
                reasoning_effort='low',
            )
            choice = response.choices[0]
            if choice.finish_reason != 'stop':
                logger.debug(
                    'Model did not stop generating naturally: %s',
                    choice,
                )
                msg = 'Model did not stop generating naturally.'
                raise ModelDidNotStopError(msg)
            content = (choice.message.content or '').strip()
            add_usage(stats, response)
            try:
                return self._parse_json_question_to_sections(content)
            except JSONDecodeError as e:
                msg = 'Unable to parse: ' + content
                raise UnableToParseResponseError(msg) from e

        return await call_with_retry(call_and_parse)

    @staticmethod
    def _parse_json_question_to_sections(content: str) -> dict[str, list[str]]:
        """Parse JSON like {"1": ["A", "B"], "2": ["C"], "3": []}.

        Raises:
            TypeError: If the repaired JSON payload is not an object.
        """
        repaired_content = repair_json(content)
        data = json.loads(repaired_content)

        if not isinstance(data, dict):
            msg = 'LLM response is not a JSON object.'
            raise TypeError(msg)
        result: dict[str, list[str]] = {}
        for id_str, section_list in data.items():
            if section_list is None:
                result[str(id_str)] = []
            elif isinstance(section_list, list):
                result[str(id_str)] = [str(s).strip() for s in section_list if s]
            else:
                result[str(id_str)] = []
        return result

