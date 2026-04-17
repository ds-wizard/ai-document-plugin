import logging


logger = logging.getLogger(__name__)


def parse_answer(answer: dict, km: dict):
    answer_type = answer["type"]
    entities = km["entities"]
    answer_entities = entities["answers"]

    if answer_type == 'AnswerReply':
        entity = answer_entities.get(answer["value"], None)
        if entity is None:
            # todo: this is strange, how can there be reply but no associated value in the km?
            logger.debug("Entity %s has no answer in the KM, strange...", answer["value"])
            return ""
        return entity["label"] + (f" ({entity['advice']})" if entity['advice'] is not None else "")
    elif answer_type == 'MultiChoiceReply':
        return ", ".join([km['entities']['choices'][answer_id]['label'] for answer_id in answer['value']])
    elif answer_type == 'IntegrationReply':
        val = answer["value"]
        if val["type"] in ["PlainType", "IntegrationLegacyType", "IntegrationType"]:
            return val["value"]
        raise RuntimeError("Unkown integration answer type", val["type"])
    elif answer_type == 'ItemListReply':
        return None  # this answer is answered in it's children
    elif answer_type == 'StringReply':
        return answer['value']  # this answer is answered in it's children
    else:
        raise RuntimeError("Unknown answer type", answer_type)
