import logging
from typing import Any

logger = logging.getLogger(__name__)


def _parse_item_select_reply(
    answer: dict[str, Any],
    km: dict[str, Any],
    replies: dict[str, Any] | None,
    question_path: str | None,
) -> str:
    selected_item_uuid = answer.get('value', '')
    if not selected_item_uuid or replies is None or question_path is None:
        return ''

    question_uuid = question_path.rsplit('.', 1)[-1]
    question = km.get('entities', {}).get('questions', {}).get(question_uuid, {})
    list_question_uuid = question.get('listQuestionUuid')
    if not list_question_uuid:
        return ''

    parent_path = question_path.rsplit('.', 1)[0]
    list_path_prefix = f'{parent_path}.{list_question_uuid}'

    for reply_path, reply_payload in replies.items():
        if not reply_path.startswith(f'{list_path_prefix}.{selected_item_uuid}.'):
            continue

        reply_question_uuid = reply_path.rsplit('.', 1)[-1]
        question_type = km.get('entities', {}).get('questions', {}).get(reply_question_uuid, {}).get('questionType')
        reply_value = reply_payload.get('value', {})

        if question_type == 'ValueQuestion':
            value = reply_value.get('value', '')
            if value:
                return value
            continue

        if question_type == 'IntegrationQuestion':
            value = reply_value.get('value', {}).get('value', '')
            if value:
                return value

    return ''


def parse_answer(  # noqa: PLR0911
    answer: dict[str, Any],
    km: dict[str, Any],
    replies: dict[str, Any] | None = None,
    question_path: str | None = None,
) -> str | None:
    answer_type = answer['type']
    entities = km['entities']
    answer_entities = entities['answers']

    if answer_type == 'AnswerReply':
        entity = answer_entities.get(answer['value'], None)
        if entity is None:
            logger.debug(
                'Entity %s has no answer in the KM, strange...',
                answer['value'],
            )
            return ''
        return entity['label'] + (f' ({entity["advice"]})' if entity['advice'] is not None else '')
    if answer_type == 'MultiChoiceReply':
        return ', '.join(
            [km['entities']['choices'][answer_id]['label'] for answer_id in answer['value']],
        )
    if answer_type == 'IntegrationReply':
        val = answer['value']
        if val['type'] in {
            'PlainType',
            'IntegrationLegacyType',
            'IntegrationType',
        }:
            return val['value']
        msg = 'Unkown integration answer type'
        raise RuntimeError(msg, val['type'])
    if answer_type == 'ItemListReply':
        return None  # this answer is answered in it's children
    if answer_type == 'StringReply':
        return answer['value']  # this answer is answered in it's children
    if answer_type == 'ItemSelectReply':
        return _parse_item_select_reply(answer, km, replies, question_path)

    msg = 'Unknown answer type'
    raise RuntimeError(msg, answer_type)
