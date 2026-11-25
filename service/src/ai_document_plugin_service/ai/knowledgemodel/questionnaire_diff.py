"""What changed between the replies stored with a generation and the replies of the questionnaire now."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import (
    ReplyType,
    StoredReply,
    build_snapshot,
)
from ai_document_plugin_service.ai.knowledgemodel.reachable_replies import reachable_replies

MAX_ITEM_TITLE_LENGTH = 80
REMOVED_OPTION = '(removed option)'


class ChangeKind(StrEnum):
    ADDED = 'added'
    CHANGED = 'changed'
    REMOVED = 'removed'


@dataclass(frozen=True)
class ReplyChange:
    path: str
    kind: ChangeKind
    old: StoredReply | None
    new: StoredReply | None


@dataclass(frozen=True)
class ChangeDescription:
    """A change in words, as shown to the user."""

    path: str
    kind: ChangeKind
    chapter_title: str | None
    question_title: str | None
    # The list items the question sits in, outermost first, e.g. the title of a dataset.
    context: list[str]
    old_value: str | None
    new_value: str | None
    # Who made the answer and when. Only known for answers that exist now.
    changed_by: str | None
    changed_at: str | None


def diff_replies(old: Iterable[StoredReply], new: Iterable[StoredReply]) -> list[ReplyChange]:
    """The replies added, changed and removed between two snapshots, ordered by path."""
    old_by_path = {reply.path: reply for reply in old}
    new_by_path = {reply.path: reply for reply in new}

    changes: list[ReplyChange] = []
    for path in sorted(old_by_path.keys() | new_by_path.keys()):
        before = old_by_path.get(path)
        after = new_by_path.get(path)
        if before is None:
            changes.append(ReplyChange(path, ChangeKind.ADDED, None, after))
        elif after is None:
            changes.append(ReplyChange(path, ChangeKind.REMOVED, before, None))
        elif not before.same_value_as(after):
            changes.append(ReplyChange(path, ChangeKind.CHANGED, before, after))
    return changes


def describe_changes(stored: Iterable[StoredReply], current_detail: dict[str, Any]) -> list[ChangeDescription]:
    """Describe what changed between ``stored`` and the questionnaire detail as DSW returns it now.

    Labels and titles come from the current knowledge model; answers and choices it no longer knows fall back to
    the label stored with the reply.
    """
    km = current_detail['knowledgeModel']
    current_replies = current_detail['replies']

    stored_by_path = {reply.path: reply for reply in stored}
    current = build_snapshot(km, current_replies)
    current_by_path = {reply.path: reply for reply in current}
    reachable = reachable_replies(km, current_replies)

    descriptions: list[ChangeDescription] = []
    for change in diff_replies(stored_by_path.values(), current):
        side = current_by_path if change.new is not None else stored_by_path
        current_reply = reachable.get(change.path) if change.new is not None else None
        descriptions.append(
            ChangeDescription(
                path=change.path,
                kind=change.kind,
                chapter_title=_chapter_title(km, change.path),
                question_title=_question_title(km, change.path),
                context=_item_context(km, change.path, side),
                old_value=_describe_value(change.old, km, stored_by_path) if change.old else None,
                new_value=_describe_value(change.new, km, current_by_path) if change.new else None,
                changed_by=_user_name((current_reply or {}).get('createdBy')),
                changed_at=(current_reply or {}).get('createdAt'),
            ),
        )
    return descriptions


def _questions(km: dict[str, Any]) -> dict[str, Any]:
    return km['entities']['questions']


def _chapter_title(km: dict[str, Any], path: str) -> str | None:
    return km['entities']['chapters'].get(path.split('.', 1)[0], {}).get('title')


def _question_title(km: dict[str, Any], path: str) -> str | None:
    return _questions(km).get(path.rsplit('.', 1)[-1], {}).get('title')


def _user_name(user: dict[str, Any] | None) -> str | None:
    if not user:
        return None
    name = f'{user.get("firstName", "")} {user.get("lastName", "")}'.strip()
    return name or None


def _item_title(km: dict[str, Any], list_path: str, item_uuid: UUID | str, side: Mapping[str, StoredReply]) -> str:
    """An item has no title of its own: it is the answer to the first question of the list's item template."""
    list_question = _questions(km).get(list_path.rsplit('.', 1)[-1], {})
    templates = list_question.get('itemTemplateQuestionUuids', [])
    if templates:
        first = side.get(f'{list_path}.{item_uuid}.{templates[0]}')
        if first is not None and first.text_value:
            title = first.text_value.strip().splitlines()[0]
            if len(title) > MAX_ITEM_TITLE_LENGTH:
                return title[: MAX_ITEM_TITLE_LENGTH - 1] + '…'
            return title
    return 'Untitled item'


def _item_context(km: dict[str, Any], path: str, side: Mapping[str, StoredReply]) -> list[str]:
    """The titles of the list items a path runs through, outermost first."""
    segments = path.split('.')
    questions = _questions(km)
    context: list[str] = []
    # The last segment is the question itself; the first is the chapter.
    for index in range(2, len(segments) - 1):
        if questions.get(segments[index - 1], {}).get('questionType') == 'ListQuestion':
            context.append(_item_title(km, '.'.join(segments[:index]), segments[index], side))
    return context


def _label(km: dict[str, Any], kind: str, uuid: UUID) -> str | None:
    label = km['entities'].get(kind, {}).get(str(uuid), {}).get('label')
    return label if isinstance(label, str) else None


def _describe_value(reply: StoredReply, km: dict[str, Any], side: Mapping[str, StoredReply]) -> str:
    if reply.reply_type == ReplyType.ANSWER:
        return _label(km, 'answers', reply.uuid_value) or reply.display_text or REMOVED_OPTION
    if reply.reply_type == ReplyType.MULTI_CHOICE:
        return _describe_choices(reply, km)
    if reply.reply_type == ReplyType.ITEM_SELECT:
        return _describe_selected_item(reply, km, side)
    if reply.reply_type == ReplyType.ITEM_LIST:
        return ', '.join(_item_title(km, reply.path, item_uuid, side) for item_uuid in reply.uuid_values or ())
    return reply.text_value or ''


def _describe_choices(reply: StoredReply, km: dict[str, Any]) -> str:
    labels = [_label(km, 'choices', choice) for choice in reply.uuid_values or ()]
    if all(labels):
        return ', '.join(label for label in labels if label)
    return reply.display_text or REMOVED_OPTION


def _describe_selected_item(reply: StoredReply, km: dict[str, Any], side: Mapping[str, StoredReply]) -> str:
    """An item-select reply names an item of another list; its title is looked up there."""
    question = _questions(km).get(reply.path.rsplit('.', 1)[-1], {})
    list_question_uuid = question.get('listQuestionUuid')
    if not list_question_uuid or reply.uuid_value is None:
        return 'Untitled item'
    list_path = f'{reply.path.rsplit(".", 1)[0]}.{list_question_uuid}'
    return _item_title(km, list_path, reply.uuid_value, side)
