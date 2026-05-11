from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import (
        BlankQuestion,
        Chapter,
        IntegrationQuestion,
        ListQuestion,
        MultiChoiceQuestion,
        OptionsQuestion,
        QuestionData,
        ValueQuestion,
    )


class QuestionVisitor(ABC):
    """Abstract visitor interface for visiting QuestionData types."""

    @abstractmethod
    def visit_value_question(self, question: 'ValueQuestion') -> list['QuestionData']:
        """Visit a ValueQuestion."""

    @abstractmethod
    def visit_list_question(self, question: 'ListQuestion') -> list['QuestionData']:
        """Visit a ListQuestion."""

    @abstractmethod
    def visit_options_question(self, question: 'OptionsQuestion') -> list['QuestionData']:
        """Visit an OptionsQuestion."""

    @abstractmethod
    def visit_multi_choice_question(
        self,
        question: 'MultiChoiceQuestion',
    ) -> list['QuestionData']:
        """Visit a MultiChoiceQuestion."""

    @abstractmethod
    def visit_integration_question(
        self,
        question: 'IntegrationQuestion',
    ) -> list['QuestionData']:
        """Visit an IntegrationQuestion."""

    @abstractmethod
    def visit_item_select_question(
        self,
        question: 'ItemSelectQuestion',
    ) -> list['QuestionData']:
        """Visit an ItemSelectQuestion."""

    @abstractmethod
    def visit_blank_question(self, question: 'BlankQuestion') -> list['QuestionData']:
        """Visit an IntegrationQuestion."""

    @abstractmethod
    def visit_chapter(self, question: 'Chapter') -> list['QuestionData']:
        """Visit an IntegrationQuestion."""
