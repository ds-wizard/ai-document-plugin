from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .question_visitor import QuestionVisitor


class QuestionnaireElement(ABC):
    @abstractmethod
    def get_path(self) -> str: ...


class QuestionData(QuestionnaireElement):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
        reply: str | None = None,
    ) -> None:
        self.path = path
        self.uuid = uuid
        self.title = title
        self.text = text
        self.parent_question = parent_question
        self.parent_answer = parent_answer
        self.reply = reply
        self.context: str | None = None

    @abstractmethod
    def accept(self, visitor: 'QuestionVisitor') -> None:
        """Accept a visitor and return the result of visiting this question."""

    def get_path(self) -> str:
        if self.parent_question is not None:
            return self.parent_question.get_path() + '.' + self.uuid
        if self.parent_answer is not None:
            return self.parent_answer.get_path() + '.' + self.uuid
        return self.uuid


class Chapter(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str,
        text: str | None,
        questions: list['QuestionData'],
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question=None,
            parent_answer=None,
        )
        self.questions = questions

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_chapter(self)


class BlankQuestion(QuestionData):
    """Wrapper question for a synthetic root that only holds child questions."""

    def __init__(self, questions: list['QuestionData']) -> None:
        super().__init__(
            path='__root__',
            uuid='__root__',
            title='Root',
            text=None,
        )
        self.questions = questions

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_blank_question(self)


class ValueQuestion(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question,
            parent_answer,
        )

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_value_question(self)


class ListQuestion(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        questions: list['QuestionData'],
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question,
            parent_answer,
        )
        self.questions = questions

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_list_question(self)

    def get_path(self) -> str:
        if self.parent_question is not None:
            return self.parent_question.get_path() + '.' + self.uuid + '.*'
        if self.parent_answer is not None:
            return self.parent_answer.get_path() + '.' + self.uuid + '.*'
        return self.uuid + '.*'


class OptionsAnswer(QuestionnaireElement):
    def __init__(
        self,
        path: str,
        uuid: str,
        label: str | None,
        followup_questions: list['QuestionData'],
        parent_question: Optional['OptionsQuestion'] = None,
    ) -> None:
        self.path = path
        self.uuid = uuid
        self.label = label
        self.followup_questions = followup_questions
        self.parent_question = parent_question

    def get_path(self) -> str:
        if self.parent_question is None:
            return self.uuid
        return self.parent_question.get_path() + '.' + self.uuid


class OptionsQuestion(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        answers: list[OptionsAnswer],
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question,
            parent_answer,
        )
        self.answers = answers

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_options_question(self)


@dataclass
class Choice:
    label: str
    uuid: str


class MultiChoiceQuestion(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        choices: list[Choice],
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question,
            parent_answer,
        )
        self.choices = choices

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_multi_choice_question(self)


class IntegrationQuestion(QuestionData):
    def __init__(
        self,
        path: str,
        uuid: str,
        title: str | None,
        text: str | None,
        parent_question: Optional['QuestionData'] = None,
        parent_answer: Optional['OptionsAnswer'] = None,
    ) -> None:
        super().__init__(
            path,
            uuid,
            title,
            text,
            parent_question,
            parent_answer,
        )

    def accept(self, visitor: 'QuestionVisitor') -> None:
        return visitor.visit_integration_question(self)
