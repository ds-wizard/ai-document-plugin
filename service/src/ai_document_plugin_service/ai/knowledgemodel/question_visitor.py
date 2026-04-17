from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import (
        ValueQuestion,
        ListQuestion,
        OptionsQuestion,
        MultiChoiceQuestion,
        IntegrationQuestion,
        BlankQuestion,
        Chapter
    )


class QuestionVisitor(ABC):
    """Abstract visitor interface for visiting QuestionData types."""

    @abstractmethod
    def visit_value_question(self, question: 'ValueQuestion'):
        """Visit a ValueQuestion."""
        pass

    @abstractmethod
    def visit_list_question(self, question: 'ListQuestion'):
        """Visit a ListQuestion."""
        pass

    @abstractmethod
    def visit_options_question(self, question: 'OptionsQuestion'):
        """Visit an OptionsQuestion."""
        pass

    @abstractmethod
    def visit_multi_choice_question(self, question: 'MultiChoiceQuestion'):
        """Visit a MultiChoiceQuestion."""
        pass

    @abstractmethod
    def visit_integration_question(self, question: 'IntegrationQuestion'):
        """Visit an IntegrationQuestion."""
        pass

    @abstractmethod
    def visit_blank_question(self, question: 'BlankQuestion'):
        """Visit an IntegrationQuestion."""
        pass

    @abstractmethod
    def visit_chapter(self, question: 'Chapter'):
        """Visit an IntegrationQuestion."""
        pass
