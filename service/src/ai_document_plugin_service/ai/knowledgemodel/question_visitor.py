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
        ValueQuestion,
    )


class QuestionVisitor(ABC):
    """Abstract visitor interface for visiting QuestionData types."""

    @abstractmethod
    def visit_value_question(self, question: 'ValueQuestion'):
        """Visit a ValueQuestion."""

    @abstractmethod
    def visit_list_question(self, question: 'ListQuestion'):
        """Visit a ListQuestion."""

    @abstractmethod
    def visit_options_question(self, question: 'OptionsQuestion'):
        """Visit an OptionsQuestion."""

    @abstractmethod
    def visit_multi_choice_question(self, question: 'MultiChoiceQuestion'):
        """Visit a MultiChoiceQuestion."""

    @abstractmethod
    def visit_integration_question(self, question: 'IntegrationQuestion'):
        """Visit an IntegrationQuestion."""

    @abstractmethod
    def visit_blank_question(self, question: 'BlankQuestion'):
        """Visit an IntegrationQuestion."""

    @abstractmethod
    def visit_chapter(self, question: 'Chapter'):
        """Visit an IntegrationQuestion."""
