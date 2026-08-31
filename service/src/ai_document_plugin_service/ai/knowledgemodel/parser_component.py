import logging
from collections.abc import Iterator

from haystack import component

from ai_document_plugin_service.ai.generation.parse_answers import parse_integration_reply_value
from ai_document_plugin_service.ai.knowledgemodel.types import (
    Chapter,
    Choice,
    IntegrationQuestion,
    ItemSelectQuestion,
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
    ItemSelectQuestion,
]

logger = logging.getLogger(__name__)
REPLY_PATH_PARTS_MIN_LENGTH = 2
REPLY_PARENT_SEGMENT_INDEX = -2


@component
class ParserComponent:
    def __init__(self) -> None:
        self.km: dict = {}

    @component.output_types(data=list[QuestionData])
    def run(self, data: dict, trigger: bool) -> dict[str, list[QuestionData]]:  # noqa: FBT001, ARG002
        self.km = data['knowledgeModel']
        replies = data['replies']
        logger.info(
            'Parsing knowledge model replies into question tree',
            extra={
                'chapter_count': len(self.km.get('chapterUuids', [])),
                'reply_count': len(replies),
            },
        )
        top_level_questions: list[QuestionData] = []
        for chapter_dict in self._iterate_km_chapters():
            parsed_chapter = self.parse_chapter(chapter_dict['uuid'], replies)
            top_level_questions.append(parsed_chapter)
        logger.info(
            'Finished parsing knowledge model replies',
            extra={'chapter_count': len(top_level_questions)},
        )
        return {'data': top_level_questions}

    def _iterate_km_chapters(self) -> Iterator[dict]:
        for chapter_uuid in self.km['chapterUuids']:
            yield self.km['entities']['chapters'][chapter_uuid]

    def parse_chapter(self, chapter_uuid: str, replies: dict) -> Chapter:
        """Parse a Chapter from the knowledge model."""
        chapter_data = self.km['entities']['chapters'][chapter_uuid]

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
            parsed_question = self.parse_question(
                question_uuid,
                replies,
                chapter.uuid + '.' + question_uuid,
                parent_question=chapter,
            )
            if parsed_question is not None:
                questions.append(parsed_question)

        chapter.questions = questions
        return chapter

    def parse_choice(self, choice_uuid: str) -> Choice:
        """Parse a Choice from the knowledge model."""
        choice_data = self.km['entities']['choices'][choice_uuid]
        return Choice(label=choice_data['label'], uuid=choice_uuid)

    def parse_options_answer(
        self,
        answer_uuid: str,
        replies: dict,
        path: str,
        parent_question: OptionsQuestion | None = None,
    ) -> OptionsAnswer:
        """Parse an OptionsAnswer from the knowledge model."""
        answer_data = self.km['entities']['answers'][answer_uuid]

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
            parsed_question = self.parse_question(
                question_uuid,
                replies,
                parent_question=None,
                parent_answer=answer,
                path=path + '.' + question_uuid,
            )
            if parsed_question is not None:
                followup_questions.append(parsed_question)

        answer.followup_questions = followup_questions
        return answer

    def parse_value_question(
        self,
        question_uuid: str,
        question: dict,
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

        value_question.reply = self.get_value_reply(replies, path)

        return value_question

    @staticmethod
    def get_value_reply(
        replies: dict,
        path: str,
    ) -> str:
        """Get the reply for the question."""
        return replies.get(path, {}).get('value', {}).get('value', '')

    def parse_integration_question(
        self,
        question_uuid: str,
        question: dict,
        replies: dict,
        path: str,
        parent_question: QuestionData | None = None,
        parent_answer: OptionsAnswer | None = None,
    ) -> IntegrationQuestion:
        """Parse an IntegrationQuestion from the knowledge model."""
        integration_question = IntegrationQuestion(
            path=path,
            uuid=question_uuid,
            title=question['title'],
            text=question.get('text'),
            parent_question=parent_question,
            parent_answer=parent_answer,
        )

        integration_question.reply = self.get_integration_reply(
            replies,
            path,
        )

        return integration_question

    @staticmethod
    def get_integration_reply(
        replies: dict,
        path: str,
    ) -> str:
        """Get the reply for the question."""
        answer = replies.get(path, {}).get('value', {})
        return parse_integration_reply_value(answer)

    def parse_list_question(
        self,
        question_uuid: str,
        question: dict,
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
            parsed_question = self.parse_question(
                nested_question_uuid,
                replies,
                path + '.*.' + nested_question_uuid,
                parent_question=list_question,
            )
            if parsed_question is not None:
                questions.append(parsed_question)

        list_question.questions = questions
        return list_question

    def parse_options_question(
        self,
        question_uuid: str,
        question: dict,
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
        answers = [
            self.parse_options_answer(
                answer_uuid,
                replies,
                path + '.' + answer_uuid,
                parent_question=options_question,
            )
            for answer_uuid in question.get('answerUuids', [])
        ]

        options_question.answers = answers

        options_question.reply = self.get_option_reply(
            replies,
            path,
        )

        return options_question

    def get_option_reply(
        self,
        replies: dict,
        path: str,
    ) -> str:
        """Get the reply for the question."""
        reply = replies.get(path, {}).get('value', {}).get('value', '')
        return self.km.get('entities', {}).get('answers', {}).get(reply, {}).get('label', '')

    def parse_multi_choice_question(
        self,
        question_uuid: str,
        question: dict,
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
            choices=[self.parse_choice(choice_uuid) for choice_uuid in question.get('choiceUuids', [])],
            parent_question=parent_question,
            parent_answer=parent_answer,
        )

        multichoice_question.reply = '\n'.join(
            self.get_multichoice_reply(replies, path),
        )

        return multichoice_question

    def get_multichoice_reply(
        self,
        replies: dict,
        path: str,
    ) -> list[str]:
        """Get the reply for the question."""
        reply_values = replies.get(path, {}).get('value', {}).get('value', '')
        return [
            self.km.get('entities', {}).get('answers', {}).get(reply_value, {}).get('label', '')
            for reply_value in reply_values
        ]

    def parse_item_select_question(
        self,
        question_uuid: str,
        question: dict,
        replies: dict,
        path: str,
        parent_question: QuestionData | None = None,
        parent_answer: OptionsAnswer | None = None,
    ) -> ItemSelectQuestion:
        """Parse an ItemSelectQuestion from the knowledge model."""
        item_select_question = ItemSelectQuestion(
            path=path,
            uuid=question_uuid,
            title=question['title'],
            text=question.get('text'),
            parent_question=parent_question,
            parent_answer=parent_answer,
        )

        item_select_question.reply = self.get_item_select_question_reply(replies, path)

        return item_select_question

    def get_item_select_question_reply(
        self,
        replies: dict,
        path: str,
    ) -> str:
        """Get the reply for the question."""
        selected_item_uuid = replies.get(path, {}).get('value', {}).get('value', '')
        if not selected_item_uuid:
            return ''

        list_path_prefix = path.split('.*.', maxsplit=1)[0] if '.*.' in path else path.rsplit('.', 1)[0]

        for reply_path, reply_payload in replies.items():
            path_parts = reply_path.split('.')
            if len(path_parts) < REPLY_PATH_PARTS_MIN_LENGTH or path_parts[REPLY_PARENT_SEGMENT_INDEX] != 'reply':
                continue
            if not reply_path.startswith(f'{list_path_prefix}.'):
                continue
            if selected_item_uuid not in path_parts:
                continue

            question_uuid = path_parts[-1]
            question_type = self.km.get('entities', {}).get('questions', {}).get(question_uuid, {}).get('questionType')

            if question_type == 'ValueQuestion':
                value = reply_payload.get('value', {}).get('value', '')
                if value:
                    return value
                continue

            if question_type == 'IntegrationQuestion':
                answer = reply_payload.get('value', {})
                value = parse_integration_reply_value(answer)
                if value:
                    return value

        return ''

    def parse_question(
        self,
        question_uuid: str,
        replies: dict,
        path: str,
        parent_question: QuestionData | None = None,
        parent_answer: OptionsAnswer | None = None,
    ) -> QuestionData | None:
        """Parse a question from the knowledge model based on its type.

        Args:
            question_uuid: UUID of the question to parse
            parent_question: Optional parent question for nested questions or
                chapter-level questions
            parent_answer: Optional parent answer (for followup questions)

        Returns:
            QuestionData instance of the appropriate type, or None for skipped question types.

        Raises:
            ValueError: If the question type is unknown.
        """
        question = self.km['entities']['questions'][question_uuid]
        question_type = question.get('questionType')
        parser_by_type = {
            'ValueQuestion': self.parse_value_question,
            'ListQuestion': self.parse_list_question,
            'OptionsQuestion': self.parse_options_question,
            'MultiChoiceQuestion': self.parse_multi_choice_question,
            'IntegrationQuestion': self.parse_integration_question,
            'ItemSelectQuestion': self.parse_item_select_question,
        }
        parser = parser_by_type.get(question_type)

        if parser is not None:
            return parser(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        if question_type == 'FileQuestion':
            logger.info('Skipping unsupported question type %s for question %s', question_type, question_uuid)
            return None

        error_message = f'Unknown question type: {question_type}'
        raise ValueError(error_message)
