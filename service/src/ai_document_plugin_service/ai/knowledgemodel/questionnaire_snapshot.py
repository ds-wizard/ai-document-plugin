"""The replies of a questionnaire in the form they are stored with a generation.

Only replies that apply to the questionnaire as it stands are kept (see ``reachable_replies``), as typed values:
what DSW sends as ``{type, value}`` becomes one of the fields of ``StoredReply``. Replies that are empty, and
replies of types that never reach a document (files), are left out, so that an empty reply and a missing one are
the same thing when two snapshots are compared.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.reachable_replies import reachable_replies

logger = logging.getLogger(__name__)


class ReplyType(StrEnum):
    """Stored in the database; changing a value requires a migration."""

    STRING = 'string'
    INTEGRATION = 'integration'
    ANSWER = 'answer'
    ITEM_SELECT = 'item_select'
    MULTI_CHOICE = 'multi_choice'
    ITEM_LIST = 'item_list'


@dataclass(frozen=True)
class StoredReply:
    """One reply. Exactly one of the three value fields is set, which one depends on the type:

    - ``text_value``: string and integration replies.
    - ``uuid_value``: answer replies (the selected answer) and item-select replies (the selected item).
    - ``uuid_values``: multi-choice replies (the selected choices) and item-list replies (the items, in order).
    """

    path: str
    reply_type: ReplyType
    text_value: str | None = None
    uuid_value: UUID | None = None
    uuid_values: tuple[UUID, ...] | None = None
    # What the value was called when it was stored, for answers and choices whose label can no longer be looked
    # up later, e.g. after the knowledge model changed. Not part of the value.
    display_text: str | None = None

    def same_value_as(self, other: 'StoredReply') -> bool:
        return (self.reply_type, self.text_value, self.uuid_value, self.uuid_values) == (
            other.reply_type,
            other.text_value,
            other.uuid_value,
            other.uuid_values,
        )


def build_snapshot(km: dict[str, Any], replies: dict[str, Any]) -> list[StoredReply]:
    """The reachable replies of a questionnaire, typed, ordered by path.

    ``km`` is the ``knowledgeModel`` of the questionnaire detail and ``replies`` its ``replies``. A reply that
    cannot be read is skipped with a warning instead of failing the caller.
    """
    snapshot: list[StoredReply] = []
    for path, reply in sorted(reachable_replies(km, replies).items()):
        try:
            stored = _to_stored_reply(path, reply.get('value', {}), km['entities'])
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.warning('Skipping a reply that cannot be stored', exc_info=True, extra={'reply_path': path})
            continue
        if stored is not None and not _is_empty(stored):
            snapshot.append(stored)
    return snapshot


def _to_stored_reply(path: str, value: dict[str, Any], entities: dict[str, Any]) -> StoredReply | None:
    reply_type = value.get('type')
    raw = value.get('value')

    if reply_type == 'StringReply':
        return StoredReply(path, ReplyType.STRING, text_value=_as_text(raw))
    if reply_type == 'IntegrationReply':
        return StoredReply(path, ReplyType.INTEGRATION, text_value=_as_text(raw['value']))
    if reply_type in {'AnswerReply', 'ItemSelectReply'}:
        return _single_uuid_reply(path, reply_type, raw, entities)
    if reply_type in {'MultiChoiceReply', 'ItemListReply'}:
        return _multiple_uuids_reply(path, reply_type, raw, entities)

    if reply_type != 'FileReply':
        logger.warning('Skipping a reply of an unknown type', extra={'reply_path': path, 'reply_type': reply_type})
    return None


def _single_uuid_reply(path: str, reply_type: str, raw: str, entities: dict[str, Any]) -> StoredReply:
    if reply_type == 'AnswerReply':
        return StoredReply(path, ReplyType.ANSWER, uuid_value=UUID(raw), display_text=_label(entities, 'answers', raw))
    return StoredReply(path, ReplyType.ITEM_SELECT, uuid_value=UUID(raw))


def _multiple_uuids_reply(path: str, reply_type: str, raw: list[str], entities: dict[str, Any]) -> StoredReply:
    uuids = tuple(UUID(value) for value in raw)
    if reply_type == 'ItemListReply':
        return StoredReply(path, ReplyType.ITEM_LIST, uuid_values=uuids)
    labels = [_label(entities, 'choices', value) for value in raw]
    return StoredReply(
        path,
        ReplyType.MULTI_CHOICE,
        uuid_values=uuids,
        display_text=', '.join(label for label in labels if label) or None,
    )


def _as_text(value: object) -> str:
    if not isinstance(value, str):
        msg = 'Expected a text reply value'
        raise TypeError(msg)
    return value


def _label(entities: dict[str, Any], kind: str, uuid: str) -> str | None:
    label = entities.get(kind, {}).get(uuid, {}).get('label')
    return label if isinstance(label, str) else None


def _is_empty(reply: StoredReply) -> bool:
    if reply.text_value is not None:
        return not reply.text_value.strip()
    if reply.uuid_values is not None:
        return not reply.uuid_values
    return False
