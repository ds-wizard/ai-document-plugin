from ai_document_plugin_service.ai.knowledgemodel.types import (
    Chapter,
    Choice,
    IntegrationQuestion,
    ListQuestion,
    MultiChoiceQuestion,
    OptionsAnswer,
    OptionsQuestion,
    QuestionData,
    ValueQuestion,
)

QUESTION_TYPES = [
    ValueQuestion,
    ListQuestion,
    OptionsQuestion,
    MultiChoiceQuestion,
]


def _iterate_km_chapters(km: dict):
    for chapter_uuid in km['chapterUuids']:
        yield km['entities']['chapters'][chapter_uuid]


def parse_questionnaire(data: dict) -> list[QuestionData]:
    km = data['knowledgeModel']
    replies = data['replies']
    top_level_questions: list[QuestionData] = []
    for chapter_dict in _iterate_km_chapters(km):
        parsed_chapter = parse_chapter(chapter_dict['uuid'], km, replies)
        top_level_questions.append(parsed_chapter)
    return top_level_questions


def parse_chapter(chapter_uuid: str, km: dict, replies: dict) -> Chapter:
    """Parse a Chapter from the knowledge model."""
    chapter_data = km['entities']['chapters'][chapter_uuid]

    # Create chapter first (without questions)
    chapter = Chapter(
        path=chapter_uuid,
        uuid=chapter_uuid,
        title=chapter_data['title'],
        text=chapter_data.get('text'),
        questions=[],
    )

    # Parse questions with this chapter as parent_question
    questions = []
    for question_uuid in chapter_data.get('questionUuids', []):
        questions.append(
            parse_question(
                question_uuid,
                km,
                replies,
                chapter.uuid + '.' + question_uuid,
                parent_question=chapter,
            ),
        )

    chapter.questions = questions
    return chapter


def parse_choice(choice_uuid: str, km: dict) -> Choice:
    """Parse a Choice from the knowledge model."""
    choice_data = km['entities']['choices'][choice_uuid]
    return Choice(label=choice_data['label'], uuid=choice_uuid)


def parse_options_answer(
    answer_uuid: str,
    km: dict,
    replies: dict,
    path: str,
    parent_question: OptionsQuestion | None = None,
) -> OptionsAnswer:
    """Parse an OptionsAnswer from the knowledge model."""
    answer_data = km['entities']['answers'][answer_uuid]

    # Create answer first (without followups)
    answer = OptionsAnswer(
        path=path,
        uuid=answer_uuid,
        label=answer_data.get('label'),
        followup_questions=[],
        parent_question=parent_question,
    )

    followup_questions = []
    for question_uuid in answer_data.get('followUpUuids', []):
        followup_questions.append(
            parse_question(
                question_uuid,
                km,
                replies,
                parent_question=None,
                parent_answer=answer,
                path=path + '.' + question_uuid,
            ),
        )

    answer.followup_questions = followup_questions
    return answer


def parse_value_question(
    question_uuid: str,
    question: dict,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> ValueQuestion:
    """Parse a ValueQuestion from the knowledge model."""
    value_question = ValueQuestion(
        path=path,
        uuid=question_uuid,
        title=question['title'],
        text=question.get('text'),
        parent_question=parent_question,
        parent_answer=parent_answer,
    )

    value_question.reply = get_value_reply(km, replies, value_question, path)

    return value_question


def get_value_reply(
    km: dict, replies: dict, question: QuestionData, path: str,
) -> str:
    """Get the reply for the question."""
    label = replies.get(path, {}).get('value', {}).get('value', '')

    return label


def parse_integration_question(
    question_uuid: str,
    question: dict,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> IntegrationQuestion:
    """Parse an IntegrationQuestion from the knowledge model."""
    # TODO
    integration_question = IntegrationQuestion(
        path=path,
        uuid=question_uuid,
        title=question['title'],
        text=question.get('text'),
        parent_question=parent_question,
        parent_answer=parent_answer,
    )

    integration_question.reply = get_integration_reply(
        km, replies, integration_question, path,
    )

    return integration_question


def get_integration_reply(
    km: dict, replies: dict, question: QuestionData, path: str,
) -> str:
    """Get the reply for the question."""
    label = (
        replies.get(path, {}).get('value', {}).get('value', {}).get('value', '')
    )

    return label


def parse_list_question(
    question_uuid: str,
    question: dict,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> ListQuestion:
    """Parse a ListQuestion from the knowledge model."""

    list_question = ListQuestion(
        path=path,
        uuid=question_uuid,
        title=question['title'],
        text=question.get('text'),
        parent_question=parent_question,
        parent_answer=parent_answer,
        questions=[],
    )
    questions = []
    for nested_question_uuid in question.get('itemTemplateQuestionUuids', []):
        questions.append(
            parse_question(
                nested_question_uuid,
                km,
                replies,
                path + '.*.' + nested_question_uuid,
                parent_question=list_question,
            ),
        )

    list_question.questions = questions
    return list_question


def parse_options_question(
    question_uuid: str,
    question: dict,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> OptionsQuestion:
    """Parse an OptionsQuestion from the knowledge model."""
    options_question = OptionsQuestion(
        path=path,
        uuid=question_uuid,
        title=question['title'],
        text=question.get('text'),
        answers=[],
        parent_question=parent_question,
        parent_answer=parent_answer,
    )

    # Parse answers with this options question as parent
    answers = []
    for answer_uuid in question.get('answerUuids', []):
        answers.append(
            parse_options_answer(
                answer_uuid,
                km,
                replies,
                path + '.' + answer_uuid,
                parent_question=options_question,
            ),
        )

    options_question.answers = answers

    options_question.reply = get_option_reply(
        km, replies, options_question, path,
    )

    return options_question


def get_option_reply(
    km: dict, replies: dict, question: QuestionData, path: str,
) -> str:
    """Get the reply for the question."""
    reply = replies.get(path, {}).get('value', {}).get('value', '')
    label = (
        km.get('entities', {})
        .get('answers', {})
        .get(reply, {})
        .get('label', '')
    )

    return label


def parse_multi_choice_question(
    question_uuid: str,
    question: dict,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> MultiChoiceQuestion:
    """Parse a MultiChoiceQuestion from the knowledge model."""
    multichoice_question = MultiChoiceQuestion(
        path=path,
        uuid=question_uuid,
        title=question['title'],
        text=question.get('text'),
        choices=[
            parse_choice(choice_uuid, km)
            for choice_uuid in question.get('choiceUuids', [])
        ],
        parent_question=parent_question,
        parent_answer=parent_answer,
    )

    multichoice_question.reply = '\n'.join(
        get_multichoice_reply(km, replies, multichoice_question, path),
    )

    return multichoice_question


def get_multichoice_reply(
    km: dict, replies: dict, question: QuestionData, path: str,
) -> list[str]:
    """Get the reply for the question."""
    replies = replies.get(path, {}).get('value', {}).get('value', '')
    labels = []
    for r in replies:
        labels.append(
            km.get('entities', {})
            .get('answers', {})
            .get(r, {})
            .get('label', ''),
        )

    return labels


def parse_question(
    question_uuid: str,
    km: dict,
    replies: dict,
    path: str,
    parent_question: QuestionData | None = None,
    parent_answer: OptionsAnswer | None = None,
) -> QuestionData:
    """
    Parse a question from the knowledge model based on its type.

    Args:
        question_uuid: UUID of the question to parse
        km: Knowledge model dictionary
        parent_question: Optional parent question (for nested questions, or Chapter for top-level questions)
        parent_answer: Optional parent answer (for followup questions)

    Returns:
        QuestionData instance of the appropriate type
    """
    question = km['entities']['questions'][question_uuid]
    question_type = question.get('questionType')

    if question_type == 'ValueQuestion':
        return parse_value_question(
            question_uuid,
            question,
            km,
            replies,
            path,
            parent_question,
            parent_answer,
        )
    if question_type == 'ListQuestion':
        return parse_list_question(
            question_uuid,
            question,
            km,
            replies,
            path,
            parent_question,
            parent_answer,
        )
    if question_type == 'OptionsQuestion':
        return parse_options_question(
            question_uuid,
            question,
            km,
            replies,
            path,
            parent_question,
            parent_answer,
        )
    if question_type == 'MultiChoiceQuestion':
        return parse_multi_choice_question(
            question_uuid,
            question,
            km,
            replies,
            path,
            parent_question,
            parent_answer,
        )
    if question_type == 'IntegrationQuestion':
        return parse_integration_question(
            question_uuid,
            question,
            km,
            replies,
            path,
            parent_question,
            parent_answer,
        )
    raise ValueError(f'Unknown question type: {question_type}')
