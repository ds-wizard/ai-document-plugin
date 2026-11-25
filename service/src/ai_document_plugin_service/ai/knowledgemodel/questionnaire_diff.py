"""What changed between the replies stored with a generation and the replies of the questionnaire now."""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ai_document_plugin_service.ai.knowledgemodel.list_items import find_list_path
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import StoredReply, build_snapshot
from ai_document_plugin_service.ai.knowledgemodel.reachable_replies import child_questions

MAX_ITEM_TITLE_LENGTH = 80
REMOVED_OPTION = '(removed option)'
NO_LONGER_IN_QUESTIONNAIRE = 'No longer in the questionnaire'


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


class NodeKind(StrEnum):
    CHAPTER = 'chapter'
    QUESTION = 'question'
    ITEM = 'item'


@dataclass(frozen=True)
class ValueChange:
    """A changed reply in words, as shown to the user."""

    kind: ChangeKind
    old_value: str | None
    new_value: str | None


@dataclass(frozen=True)
class ChangeNode:
    """A chapter, question or list item of the questionnaire with changes in it, in the questionnaire's order."""

    path: str
    kind: NodeKind
    title: str | None
    # The change of this node's own reply, e.g. the items of a list when some of them changed too.
    change: ValueChange | None = None
    # For an options question that did not change itself but has changed follow-up questions: the selected answer.
    # When the answer did change, the follow-ups of the old answer are all removed and those of the new one added,
    # so the change says which answer each belongs to.
    answer: str | None = None
    children: tuple['ChangeNode', ...] = ()


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


def change_tree(stored: Iterable[StoredReply], current_detail: dict[str, Any]) -> list[ChangeNode]:
    """The changes between ``stored`` and the questionnaire detail as DSW returns it now, as a tree.

    What changed is what ``diff_replies`` says. Where each change goes comes from walking the current knowledge
    model, following the stored and the current replies together, so the tree has the questionnaire's order: the
    follow-up questions of both the old and the new answer sit under their question, and the questions of both
    deleted and added items under the list. A change the walk does not reach, e.g. the reply to a question the
    knowledge model no longer has, goes into a last group of its own.

    Labels and titles come from the current knowledge model; answers and choices it no longer knows fall back to
    the label stored with the reply.
    """
    km = current_detail['knowledgeModel']
    old = {reply.path: reply for reply in stored}
    current = build_snapshot(km, current_detail['replies'])
    new = {reply.path: reply for reply in current}
    walk = _Walk(km, old, new, {change.path: change for change in diff_replies(old.values(), current)})

    tree = [node for chapter_uuid in km['chapterUuids'] if (node := walk.chapter(chapter_uuid)) is not None]
    placed = {node.path for node in _all_nodes(tree) if node.change is not None}
    unplaced = tuple(
        ChangeNode(path, NodeKind.QUESTION, _question_title(km, path), change=walk.value_change(change))
        for path, change in walk.changes.items()
        if path not in placed
    )
    if unplaced:
        tree.append(ChangeNode('', NodeKind.CHAPTER, NO_LONGER_IN_QUESTIONNAIRE, children=unplaced))
    return tree


@dataclass(frozen=True)
class _Walk:
    km: dict[str, Any]
    old: Mapping[str, StoredReply]
    new: Mapping[str, StoredReply]
    changes: Mapping[str, ReplyChange]

    def chapter(self, chapter_uuid: str) -> ChangeNode | None:
        chapter = self.km['entities']['chapters'].get(chapter_uuid, {})
        question_uuids = chapter.get('questionUuids', [])
        children = self._question_nodes((uuid, f'{chapter_uuid}.{uuid}') for uuid in question_uuids)
        return ChangeNode(chapter_uuid, NodeKind.CHAPTER, chapter.get('title'), children=children) if children else None

    def _question_nodes(self, questions: Iterable[tuple[str, str]]) -> tuple[ChangeNode, ...]:
        nodes = (self._question(question_uuid, path) for question_uuid, path in questions)
        return tuple(node for node in nodes if node is not None)

    def _question(self, question_uuid: str, path: str) -> ChangeNode | None:
        """The question with the changes under it, or None when nothing in it changed."""
        entities = self.km['entities']
        question = entities['questions'].get(question_uuid)
        if question is None:
            return None

        # What is under the question with the old reply and with the new one, e.g. the follow-ups of both answers.
        old, new = self.old.get(path), self.new.get(path)
        below = child_questions(entities, question, path, old.value if old else None)
        below += child_questions(entities, question, path, new.value if new else None)
        children = self._question_nodes(dict.fromkeys(below))
        if question.get('questionType') == 'ListQuestion':
            children = self._items(path, children)

        change = self.changes.get(path)
        if change is None and not children:
            return None
        return ChangeNode(
            path,
            NodeKind.QUESTION,
            question.get('title'),
            change=self.value_change(change) if change else None,
            answer=None if change else self._answer(new),
            children=children,
        )

    def _items(self, list_path: str, questions: tuple[ChangeNode, ...]) -> tuple[ChangeNode, ...]:
        """The changed questions of a list grouped by the item they belong to."""
        by_item: dict[str, list[ChangeNode]] = {}
        for node in questions:
            by_item.setdefault(node.path[len(list_path) + 1 :].split('.', 1)[0], []).append(node)
        current_items = _strings(self.new[list_path].raw) if list_path in self.new else []
        return tuple(
            ChangeNode(
                f'{list_path}.{item_uuid}',
                NodeKind.ITEM,
                _item_title(self.km, list_path, item_uuid, self.new if item_uuid in current_items else self.old),
                children=tuple(nodes),
            )
            for item_uuid, nodes in by_item.items()
        )

    def _answer(self, reply: StoredReply | None) -> str | None:
        """The label of the answer an options reply selects."""
        if reply is None or reply.reply_type != 'AnswerReply':
            return None
        return _label(self.km, 'answers', reply.raw) or reply.display_text or REMOVED_OPTION

    def value_change(self, change: ReplyChange) -> ValueChange:
        return ValueChange(
            kind=change.kind,
            old_value=_describe_value(change.old, self.km, self.old) if change.old is not None else None,
            new_value=_describe_value(change.new, self.km, self.new) if change.new is not None else None,
        )


def _all_nodes(nodes: Iterable[ChangeNode]) -> Iterator[ChangeNode]:
    for node in nodes:
        yield node
        yield from _all_nodes(node.children)


def _questions(km: dict[str, Any]) -> dict[str, Any]:
    return km['entities']['questions']


def _question_title(km: dict[str, Any], path: str) -> str | None:
    return _questions(km).get(path.rsplit('.', 1)[-1], {}).get('title')


def _item_title(km: dict[str, Any], list_path: str, item_uuid: str, side: Mapping[str, StoredReply]) -> str:
    """An item has no title of its own: it is the answer to the first question of the list's item template."""
    list_question = _questions(km).get(list_path.rsplit('.', 1)[-1], {})
    templates = list_question.get('itemTemplateQuestionUuids', [])
    if templates:
        first = side.get(f'{list_path}.{item_uuid}.{templates[0]}')
        text = _text(first) if first is not None else None
        if text and text.strip():
            title = text.strip().splitlines()[0]
            if len(title) > MAX_ITEM_TITLE_LENGTH:
                return title[: MAX_ITEM_TITLE_LENGTH - 1] + '…'
            return title
    return 'Untitled item'


def _label(km: dict[str, Any], kind: str, uuid: object) -> str | None:
    if not isinstance(uuid, str):
        return None
    label = km['entities'].get(kind, {}).get(uuid, {}).get('label')
    return label if isinstance(label, str) else None


def _strings(raw: object) -> list[str]:
    """The UUIDs of a multi-choice or item-list reply."""
    return [value for value in raw if isinstance(value, str)] if isinstance(raw, list) else []


def _text(reply: StoredReply) -> str | None:
    """The text of a string reply, or the text an integration reply shows."""
    raw = reply.raw
    if reply.reply_type == 'IntegrationReply' and isinstance(raw, dict):
        raw = raw.get('value')
    return raw if isinstance(raw, str) else None


def _describe_value(reply: StoredReply, km: dict[str, Any], side: Mapping[str, StoredReply]) -> str:
    if reply.reply_type == 'AnswerReply':
        return _label(km, 'answers', reply.raw) or reply.display_text or REMOVED_OPTION
    if reply.reply_type == 'MultiChoiceReply':
        return _describe_choices(reply, km)
    if reply.reply_type == 'ItemSelectReply':
        return _describe_selected_item(reply, km, side)
    if reply.reply_type == 'ItemListReply':
        return ', '.join(_item_title(km, reply.path, item_uuid, side) for item_uuid in _strings(reply.raw))
    return _text(reply) or ''


def _describe_choices(reply: StoredReply, km: dict[str, Any]) -> str:
    labels = [_label(km, 'choices', choice) for choice in _strings(reply.raw)]
    if labels and all(labels):
        return ', '.join(label for label in labels if label)
    return reply.display_text or REMOVED_OPTION


def _describe_selected_item(reply: StoredReply, km: dict[str, Any], side: Mapping[str, StoredReply]) -> str:
    """An item-select reply names an item of another list; its title is looked up there."""
    question = _questions(km).get(reply.path.rsplit('.', 1)[-1], {})
    list_question_uuid = question.get('listQuestionUuid')
    if not list_question_uuid or not isinstance(reply.raw, str):
        return 'Untitled item'
    list_path = find_list_path(list_question_uuid, reply.raw, ((path, r.value) for path, r in side.items()))
    if list_path is None:
        return 'Untitled item'
    return _item_title(km, list_path, reply.raw, side)
