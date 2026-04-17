import json
import logging
from abc import abstractmethod, ABC
from json import JSONDecodeError

from json_repair import repair_json
from openai import OpenAI

from ai_document_plugin_service.ai.common import AssignmentStats
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import extract_usage_tokens, call_with_retry, add_usage

logger = logging.getLogger(__name__)


class LayerMatcher(ABC):
    @abstractmethod
    def match_questions_to_sections(
            self,
            sections_xml: str,
            question_chunk_xml: str,
            stats: AssignmentStats
    ) -> dict[str, list[str]]:
        """Return question_id -> list[section_id]."""
        pass


class OpenAILayerMatcher(LayerMatcher):
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.api_url)

    def match_questions_to_sections(
            self,
            sections_xml: str,
            question_chunk_xml: str,
            stats: AssignmentStats
    ) -> dict[str, list[str]]:
        user_message = (self.config.assignment.user_message
                        .replace("{question_text}", question_chunk_xml)
                        .replace("{sections_list}", sections_xml))
        messages = [
            {"role": "system", "content": self.config.assignment.system_message},
            {"role": "user", "content": user_message},
        ]

        def call_and_parse():
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.assignment.temperature,
                max_tokens=self.config.assignment.max_tokens,
                reasoning_effort="low",
            )
            choice = response.choices[0]
            if choice.finish_reason != "stop":
                logger.debug("Model did not stop generating naturally: %s", choice)
                raise Exception("Model did not stop generating naturally.")
            content = (choice.message.content or "").strip()
            add_usage(stats, response)
            try:
                question_to_sections = self._parse_json_question_to_sections(content)
            except JSONDecodeError as e:
                raise Exception("Unable to parse: " + content) from e
            return question_to_sections

        return call_with_retry(call_and_parse)

    @staticmethod
    def _parse_json_question_to_sections(content: str) -> dict[str, list[str]]:
        """Parse JSON like { "1": ["A", "B"], "2": ["C"], "3": [] } (section IDs are letters)."""
        repaired_content = repair_json(content)
        data = json.loads(repaired_content)

        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object.")
        result: dict[str, list[str]] = {}
        for id_str, section_list in data.items():
            if section_list is None:
                result[str(id_str)] = []
            elif isinstance(section_list, list):
                result[str(id_str)] = [str(s).strip() for s in section_list if s]
            else:
                result[str(id_str)] = []
        return result
