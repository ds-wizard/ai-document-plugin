from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict
from uuid import UUID


class AssignmentQuestionNode(TypedDict, total=False):
    question_path: str
    question_title: str
    question_text: str
    children: dict[str, 'AssignmentQuestionNode']
    include: bool
    value: bool


AssignmentTree = dict[str, AssignmentQuestionNode]


class SerializedSectionAssignment(TypedDict):
    id: str
    title: str
    assignments: AssignmentTree | None
    children: list['SerializedSectionAssignment'] | None


class SectionNode:
    """Represents a section with a reference to its parent section.
    This allows navigation up the hierarchy tree.
    """

    def __init__(self, section_dict: dict[str, Any]) -> None:
        self.section = section_dict
        self.title = section_dict['title']
        self.content = section_dict.get('content')
        self.subsections = section_dict.get('sections', [])


@dataclass
class SectionRecord:
    """A section in the template tree. Either a leaf or a parent (children set).

    `id` is a synthetic identifier minted at JSON-load time and is unique across the tree.
    `title` is the human-readable label and may collide with sibling/cousin titles.
    """

    id: UUID
    title: str
    section: SectionNode
    children: list['SectionRecord'] | None = None  # non-leaf: nested sections


@dataclass
class SectionAssignment:
    """Assignment result for one section. Either a leaf (assignments set) or a parent (children set).

    `id` mirrors the synthetic identifier from the corresponding `SectionRecord` and is the
    authoritative key for downstream processing. `title` is kept alongside for human-readable output.
    """

    id: UUID
    title: str
    assignments: AssignmentTree | None = None  # leaf: matched questions
    children: list['SectionAssignment'] | None = None  # non-leaf: nested section assignments

    def to_dict(self) -> SerializedSectionAssignment:
        return {
            'id': str(self.id),
            'title': self.title,
            'assignments': self.assignments or None,
            'children': [c.to_dict() for c in self.children] if self.children else None,
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
