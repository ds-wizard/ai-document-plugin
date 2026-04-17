"""Visitor that returns direct child questions for each question type."""

from .question_visitor import QuestionVisitor
from .types import Chapter, BlankQuestion


class DirectSubquestionVisitor(QuestionVisitor):
    def visit_chapter(self, question: Chapter):
        return question.questions

    def visit_blank_question(self, question: BlankQuestion):
        return list(question.questions)

    def visit_value_question(self, question):
        return []

    def visit_list_question(self, question):
        if not question.questions:
            return []
        return question.questions

    def visit_options_question(self, question):
        res = []
        for answer in question.answers:
            res.extend(answer.followup_questions)
        return res

    def visit_multi_choice_question(self, question):
        return []

    def visit_integration_question(self, question):
        return []
