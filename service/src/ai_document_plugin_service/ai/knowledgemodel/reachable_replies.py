"""
Filter questionnaire replies down to those that apply to the questionnaire as it stands.

DSW keeps replies that no longer apply: after an options question is switched to another answer, the replies to
the follow-up questions of the previous answer stay in the data. This walks the knowledge model from the
chapters and keeps only the replies on a path that the other replies lead to.
"""

from typing import Any


def reachable_replies(km: dict[str, Any], replies: dict[str, Any]) -> dict[str, Any]:
    """Return the replies that apply to the questionnaire, keyed by their path and otherwise untouched.

    ``km`` is the ``knowledgeModel`` of the questionnaire detail and ``replies`` its ``replies``. A reply is kept
    when its question exists in the knowledge model and every option answer and list item on its path is the one
    currently selected. An item-select reply whose item has since been deleted is kept as it is; it is a reply of
    a reachable question.

    The replies keep the order of ``replies``: document generation takes the order of list items from it.
    """
    entities = km['entities']
    reachable: set[str] = set()

    stack: list[tuple[str, str]] = []
    for chapter_uuid in km['chapterUuids']:
        chapter = entities['chapters'].get(chapter_uuid, {})
        stack.extend(
            (question_uuid, f'{chapter_uuid}.{question_uuid}') for question_uuid in chapter.get('questionUuids', [])
        )

    while stack:
        question_uuid, path = stack.pop()
        question = entities['questions'].get(question_uuid)
        if question is None:
            continue
        reply = replies.get(path)
        if reply is not None:
            reachable.add(path)
        stack.extend(_child_questions(entities, question, path, reply))

    return {path: reply for path, reply in replies.items() if path in reachable}


def _child_questions(
    entities: dict[str, Any],
    question: dict[str, Any],
    path: str,
    reply: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    """The questions below a question as ``(question uuid, path)``, given the reply to it."""
    value = reply.get('value', {}) if reply is not None else {}
    question_type = question.get('questionType')

    if question_type == 'OptionsQuestion' and value.get('type') == 'AnswerReply':
        answer_uuid = value['value']
        answer = entities['answers'].get(answer_uuid, {})
        return [(follow_up, f'{path}.{answer_uuid}.{follow_up}') for follow_up in answer.get('followUpUuids', [])]

    if question_type == 'ListQuestion' and value.get('type') == 'ItemListReply':
        return [
            (template_question, f'{path}.{item_uuid}.{template_question}')
            for item_uuid in value['value']
            for template_question in question.get('itemTemplateQuestionUuids', [])
        ]

    return []
