from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict


class AssignmentQuestionNode(TypedDict, total=False):
    question_path: str
    question_title: str
    question_text: str
    children: dict[str, 'AssignmentQuestionNode']
    include: bool
    value: bool


AssignmentTree = dict[str, AssignmentQuestionNode]


class SectionNode:
    """Represents a section with a reference to its parent section.
    This allows navigation up the hierarchy tree.
    """

    def __init__(self, section_dict) -> None:
        self.section = section_dict
        self.title = section_dict['title']
        self.content = section_dict.get('content')
        self.subsections = section_dict.get('sections', [])


@dataclass
class SectionRecord:
    """A section in the template tree. Either a leaf (text set) or a parent (children set)."""

    key: str
    section: SectionNode
    text: str | None = None  # leaf: formatted content for matching
    children: list['SectionRecord'] | None = None  # non-leaf: nested sections


@dataclass
class SectionAssignment:
    """Assignment result for one section. Either a leaf (assignments set) or a parent (children set)."""

    key: str
    assignments: AssignmentTree | None = None  # leaf: matched questions
    children: list['SectionAssignment'] | None = (
        None  # non-leaf: nested section assignments
    )

    def to_dict(self) -> dict:
        return {
            'key': self.key,
            'assignments': self.assignments or None,
            'children': [c.to_dict() for c in self.children]
            if self.children
            else None,
        }


@dataclass
class AssignmentNode:
    question_path: str
    question_title: str
    question_text: str
    status: 'AssignmentStatus'
    children: list['AssignmentNode']

    def to_dict(self) -> dict:
        return {
            'question_path': self.question_path,
            'question_title': self.question_title,
            'question_text': self.question_text,
            'status': self.status.value,
            'children': [child.to_dict() for child in self.children],
        }


class AssignmentStatus(StrEnum):
    DENIED = 'denied'
    MATCHED_EXPAND = 'matched-expand'
    MATCHED_LEAF = 'matched-leaf'
