import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)
RAW_URL_PATTERN = re.compile(r'https?://[^\s)]+')


def _strip_markdown_images(raw_value: str) -> str:
    result: list[str] = []
    i = 0
    length = len(raw_value)

    while i < length:
        if raw_value.startswith('![', i):
            alt_end = raw_value.find(']', i + 2)
            if alt_end == -1 or alt_end + 1 >= length or raw_value[alt_end + 1] != '(':
                result.append(raw_value[i])
                i += 1
                continue

            depth = 1
            j = alt_end + 2
            while j < length and depth > 0:
                if raw_value[j] == '(':
                    depth += 1
                elif raw_value[j] == ')':
                    depth -= 1
                j += 1

            if depth == 0:
                i = j
                continue

        result.append(raw_value[i])
        i += 1

    return ''.join(result)


def _extract_first_non_data_url(raw_value: str) -> str | None:
    plain_url_match = RAW_URL_PATTERN.search(_strip_markdown_images(raw_value))
    if plain_url_match is not None:
        return plain_url_match.group(0)

    return raw_value


def _normalize_whitespace(value: str) -> str:
    return ' '.join(value.split())


def _as_non_empty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _extract_url_from_raw_mapping(raw_value: dict[str, Any]) -> str | None:
    homepage = None
    for key in ('homepage', 'url', 'urlPattern'):
        candidate = _as_non_empty_string(raw_value.get(key))
        if candidate is not None and candidate.startswith(('http://', 'https://')):
            homepage = candidate
            break

    doi = _as_non_empty_string(raw_value.get('doi'))
    if doi is not None:
        stripped_doi = doi
        if homepage is not None:
            return f'{homepage}, DOI: {stripped_doi}'
        if stripped_doi.startswith(('http://', 'https://')):
            return stripped_doi
        return f'DOI: {stripped_doi}'

    if homepage is not None:
        return homepage

    for candidate in raw_value.values():
        if not isinstance(candidate, str):
            continue
        extracted_url = _extract_first_non_data_url(candidate)
        if extracted_url is not None:
            return extracted_url

    return None


def parse_integration_reply_value(answer: dict[str, Any]) -> str:
    value = answer.get('value', {})

    if value.get('type') == 'PlainType':
        return value.get('value', '')
    if value.get('type') == 'IntegrationType':
        nested_raw_value = value.get('raw')
        nested_value = value.get('value', '')
        extracted_url = _extract_first_non_data_url(nested_value)

        raw_json = json.dumps(nested_raw_value, ensure_ascii=False)
        if extracted_url is not None:
            return f'{raw_json} {extracted_url}'
        return raw_json

    logger.warning('Unknown integration answer type: %s', value.get('type'))
    return ''


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
            value = parse_integration_reply_value(reply_value)
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
        return parse_integration_reply_value(answer)
    if answer_type == 'ItemListReply':
        return None  # this answer is answered in it's children
    if answer_type == 'StringReply':
        return answer['value']  # this answer is answered in it's children
    if answer_type == 'ItemSelectReply':
        return _parse_item_select_reply(answer, km, replies, question_path)

    msg = 'Unknown answer type'
    raise RuntimeError(msg, answer_type)
