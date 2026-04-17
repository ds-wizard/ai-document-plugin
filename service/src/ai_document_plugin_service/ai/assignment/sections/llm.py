import json
from abc import abstractmethod, ABC
from json import JSONDecodeError

from json_repair import repair_json
from openai import OpenAI
from tqdm import tqdm

from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import extract_usage_tokens, call_with_retry, add_usage
from ai_document_plugin_service.ai.common.types import AssignmentStats


class SectionIdGenerator(ABC):
    @abstractmethod
    def generate_leaf_section_ids(
            self,
            leaf_sections: list[tuple[str, str]],
            stats: AssignmentStats,
    ) -> dict[str, str] | None:
        """Return section_key -> section_id, or None to use generated letter IDs."""
        pass


class OpenAISectionIdGenerator(SectionIdGenerator):
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.api_url)

    def generate_leaf_section_ids(
            self,
            leaf_sections: list[tuple[str, str]],
            stats: AssignmentStats,
    ) -> dict[str, str] | None:
        """One LLM call per leaf section: generate a short meaningful unique id. Returns section_key -> id, or None if config not set (caller should use letter ids)."""
        system_msg = self.config.section_id.system_message
        user_tpl = self.config.section_id.user_message
        result: dict[str, str] = {}
        used_ids: set[str] = set()

        for section_key, section_text in tqdm(leaf_sections):
            existing_str = ", ".join(sorted(used_ids)) if used_ids else "(none yet)"
            # Use full section text (format_section: [PARENT SECTION], Title, Content, [MOST SPECIFIC SECTION], ...) so structure and parent bodies are preserved
            content_block = (section_text or "").strip() if section_text else ""
            user_msg = (
                user_tpl.replace("{existing_ids}", existing_str)
                .replace("{section_title}", section_key)
                .replace("{section_content}", content_block)
            )
            response = call_with_retry(
                lambda um=user_msg: self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": um},
                    ],
                    reasoning_effort="low",
                    temperature=self.config.section_id.temperature,
                    max_tokens=self.config.section_id.max_tokens,
                )
            )
            add_usage(stats, response)
            choice = response.choices[0]
            raw = (choice.message.content or "").strip().splitlines()[0].strip()
            sid = _normalize_section_id(raw)
            if not sid:
                sid = f"s{len(result) + 1}"
            while sid in used_ids:
                sid = f"{sid}_{len(used_ids)}"
            used_ids.add(sid)
            result[section_key] = sid

        return result


def _normalize_section_id(raw: str) -> str:
    """Short alphanumeric + hyphen/underscore id, or empty if nothing usable."""
    s = "".join(c for c in raw if c.isalnum() or c in "-_").strip("-_") or raw[:12]
    return s[:24] if s else ""
