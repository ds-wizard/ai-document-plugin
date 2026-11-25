"""The replies of a questionnaire in the form they are stored with a generation.

Only replies that apply to the questionnaire as it stands are kept (see ``reachable_replies``), each with its value
exactly as DSW sends it (``{type, value}``), so that anything in a reply that can reach the document is compared.
Replies that are empty, and replies of types that never reach a document (files), are left out, so that an empty
reply and a missing one are the same thing when two snapshots are compared.
"""

import logging
from dataclasses import dataclass
from typing import Any

from ai_document_plugin_service.ai.knowledgemodel.reachable_replies import reachable_replies

logger = logging.getLogger(__name__)

# Reply types whose value never reaches a document.
_LEFT_OUT_REPLY_TYPES = frozenset({'FileReply'})


@dataclass(frozen=True)
class StoredReply:
    """One reply."""

    path: str
    # The value of the reply as DSW sends it, e.g. ``{'type': 'AnswerReply', 'value': '<answer uuid>'}``.
    value: dict[str, Any]
    # What the value was called when it was stored, for answers and choices whose label can no longer be looked
    # up later, e.g. after the knowledge model changed. Not part of the value.
    display_text: str | None = None

    @property
    def reply_type(self) -> str | None:
        reply_type = self.value.get('type')
        return reply_type if isinstance(reply_type, str) else None

    @property
    def raw(self) -> object:
        """The ``value`` inside the value: text, a UUID, a list of UUIDs or, for integrations, a mapping."""
        return self.value.get('value')

    def same_value_as(self, other: 'StoredReply') -> bool:
        return self.value == other.value


def build_snapshot(km: dict[str, Any], replies: dict[str, Any]) -> list[StoredReply]:
    """The reachable replies of a questionnaire, ordered by path.

    ``km`` is the ``knowledgeModel`` of the questionnaire detail and ``replies`` its ``replies``. A reply without
    a typed value is skipped with a warning instead of failing the caller.
    """
    entities = km['entities']
    snapshot: list[StoredReply] = []
    for path, reply in sorted(reachable_replies(km, replies).items()):
        value = reply.get('value')
        if not isinstance(value, dict) or not isinstance(value.get('type'), str):
            logger.warning('Skipping a reply without a typed value', extra={'reply_path': path})
            continue
        if value['type'] in _LEFT_OUT_REPLY_TYPES or _is_empty(value.get('value')):
            continue
        snapshot.append(StoredReply(path, value, _display_text(value, entities)))
    return snapshot


def _is_empty(raw: object) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        return not raw.strip()
    if isinstance(raw, list):
        return not raw
    if isinstance(raw, dict):
        # An integration reply: ``{type, value, raw?}``, empty when it has neither text nor a record.
        return _is_empty(raw.get('value')) and not raw.get('raw')
    return False


def _display_text(value: dict[str, Any], entities: dict[str, Any]) -> str | None:
    reply_type, raw = value['type'], value.get('value')
    if reply_type == 'AnswerReply' and isinstance(raw, str):
        return entity_label(entities, 'answers', raw)
    if reply_type == 'MultiChoiceReply' and isinstance(raw, list):
        labels = [entity_label(entities, 'choices', choice) for choice in raw]
        return ', '.join(label for label in labels if label) or None
    return None


def entity_label(entities: dict[str, Any], kind: str, uuid: object) -> str | None:
    """The label of an answer or choice in the knowledge model, or None when it has none (any more)."""
    if not isinstance(uuid, str):
        return None
    label = entities.get(kind, {}).get(uuid, {}).get('label')
    return label if isinstance(label, str) else None
