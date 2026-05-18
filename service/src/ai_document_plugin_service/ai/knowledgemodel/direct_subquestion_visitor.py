"""Visitor that returns direct child questions for each question type."""

from typing import override

from .question_visitor import QuestionVisitor
from .types import (
    BlankQuestion,
    Chapter,
    IntegrationQuestion,
    ItemSelectQuestion,
    ListQuestion,
    MultiChoiceQuestion,
    OptionsQuestion,
    QuestionData,
    ValueQuestion,
)


class DirectSubquestionVisitor(QuestionVisitor):
    @override
    def visit_chapter(self, question: Chapter) -> list[QuestionData]:
        return question.questions

    @override
    def visit_blank_question(self, question: BlankQuestion) -> list[QuestionData]:
        return list(question.questions)

    @override
    def visit_value_question(self, question: ValueQuestion) -> list[QuestionData]:
        _ = question
        return []

    @override
    def visit_list_question(self, question: ListQuestion) -> list[QuestionData]:
        if not question.questions:
            return []
        return question.questions

    @override
    def visit_options_question(self, question: OptionsQuestion) -> list[QuestionData]:
        res: list[QuestionData] = []
        for answer in question.answers:
            res.extend(answer.followup_questions)
        return res

    @override
    def visit_multi_choice_question(
        self,
        question: MultiChoiceQuestion,
    ) -> list[QuestionData]:
        _ = question
        return []

    @override
    def visit_integration_question(
        self,
        question: IntegrationQuestion,
    ) -> list[QuestionData]:
        _ = question
        return []

    @override
    def visit_item_select_question(
        self,
        question: ItemSelectQuestion,
    ) -> list[QuestionData]:
        _ = question
        return []
