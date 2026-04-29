from collections.abc import Iterator

from haystack import component

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


@component
class ParserComponent:
    def __init__(self) -> None:
        self.km: dict = {}

    @component.output_types(data=list[QuestionData])
    def run(self, data: dict, trigger: bool = True) -> dict[str, list[QuestionData]]:  # noqa: FBT001, FBT002, ARG002
        self.km = data['knowledgeModel']
        replies = data['replies']
        top_level_questions: list[QuestionData] = []
        for chapter_dict in self._iterate_km_chapters():
            parsed_chapter = self.parse_chapter(chapter_dict['uuid'], replies)
            top_level_questions.append(parsed_chapter)
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
        questions = [
            self.parse_question(
                question_uuid,
                replies,
                chapter.uuid + '.' + question_uuid,
                parent_question=chapter,
            )
            for question_uuid in chapter_data.get('questionUuids', [])
        ]

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

        followup_questions = [
            self.parse_question(
                question_uuid,
                replies,
                parent_question=None,
                parent_answer=answer,
                path=path + '.' + question_uuid,
            )
            for question_uuid in answer_data.get('followUpUuids', [])
        ]

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

        value_question.reply = self.get_value_reply(replies, value_question, path)

        return value_question

    @staticmethod
    def get_value_reply(
        replies: dict,
        _question: QuestionData,
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
            integration_question,
            path,
        )

        return integration_question

    @staticmethod
    def get_integration_reply(
        replies: dict,
        _question: QuestionData,
        path: str,
    ) -> str:
        """Get the reply for the question."""
        return replies.get(path, {}).get('value', {}).get('value', {}).get('value', '')

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
        questions = [
            self.parse_question(
                nested_question_uuid,
                replies,
                path + '.*.' + nested_question_uuid,
                parent_question=list_question,
            )
            for nested_question_uuid in question.get('itemTemplateQuestionUuids', [])
        ]

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
            options_question,
            path,
        )

        return options_question

    def get_option_reply(
        self,
        replies: dict,
        _question: QuestionData,
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
            self.get_multichoice_reply(replies, multichoice_question, path),
        )

        return multichoice_question

    def get_multichoice_reply(
        self,
        replies: dict,
        _question: QuestionData,
        path: str,
    ) -> list[str]:
        """Get the reply for the question."""
        reply_values = replies.get(path, {}).get('value', {}).get('value', '')
        return [
            self.km.get('entities', {}).get('answers', {}).get(reply_value, {}).get('label', '')
            for reply_value in reply_values
        ]

    def parse_question(
        self,
        question_uuid: str,
        replies: dict,
        path: str,
        parent_question: QuestionData | None = None,
        parent_answer: OptionsAnswer | None = None,
    ) -> QuestionData:
        """Parse a question from the knowledge model based on its type.

        Args:
            question_uuid: UUID of the question to parse
            parent_question: Optional parent question for nested questions or
                chapter-level questions
            parent_answer: Optional parent answer (for followup questions)

        Returns:
            QuestionData instance of the appropriate type

        Raises:
            ValueError: If the question type is unknown.

        """
        question = self.km['entities']['questions'][question_uuid]
        question_type = question.get('questionType')

        if question_type == 'ValueQuestion':
            return self.parse_value_question(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        if question_type == 'ListQuestion':
            return self.parse_list_question(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        if question_type == 'OptionsQuestion':
            return self.parse_options_question(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        if question_type == 'MultiChoiceQuestion':
            return self.parse_multi_choice_question(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        if question_type == 'IntegrationQuestion':
            return self.parse_integration_question(
                question_uuid,
                question,
                replies,
                path,
                parent_question,
                parent_answer,
            )
        error_message = f'Unknown question type: {question_type}'
        raise ValueError(error_message)
