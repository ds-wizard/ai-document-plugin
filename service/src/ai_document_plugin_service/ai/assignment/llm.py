import json
import logging
import pathlib
from abc import ABC, abstractmethod
from dataclasses import asdict
from json import JSONDecodeError
from typing import TYPE_CHECKING

from json_repair import repair_json
from openai import OpenAI

from ai_document_plugin_service.ai.common import AssignmentStats
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import (
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
    def match_questions_to_sections(
        self,
        sections_xml: str,
        question_chunk_xml: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        """Return question_id -> list[section_id]."""


class OpenAILayerMatcher(LayerMatcher):
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.api_url)

    def match_questions_to_sections(
        self,
        sections_xml: str,
        question_chunk_xml: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
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
        messages: list[ChatCompletionMessageParam] = [
            system_message,
            user_prompt,
        ]

        def call_and_parse() -> dict[str, list[str]]:
            response = self.client.chat.completions.create(
                model=self.config.model,
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
                question_to_sections = self._parse_json_question_to_sections(
                    content,
                )
            except JSONDecodeError as e:
                msg = 'Unable to parse: ' + content
                raise UnableToParseResponseError(msg) from e
            return question_to_sections

        return call_with_retry(call_and_parse)

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
                result[str(id_str)] = [
                    str(s).strip() for s in section_list if s
                ]
            else:
                result[str(id_str)] = []
        return result


class LoggingNoopLayerMatcher(LayerMatcher):
    """Logs assignment inputs to logger and a JSONL file; returns no mappings."""

    def __init__(self, log_path: str | pathlib.Path) -> None:
        self._log_path = pathlib.Path(log_path)

    def match_questions_to_sections(
        self,
        sections_xml: str,
        question_chunk_xml: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        record = {
            'sections_xml': sections_xml,
            'question_chunk_xml': question_chunk_xml,
            'stats': asdict(stats),
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        logger.info(
            'LoggingNoopLayerMatcher appended inputs to %s stats=%s',
            self._log_path,
            stats,
        )
        return {}
