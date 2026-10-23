from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict
from uuid import UUID

from ai_document_plugin_service.ai.common.types import TemplateSection


class AssignmentQuestionNode(TypedDict, total=False):
    question_path: str
    question_title: str
    question_text: str
    children: dict[str, 'AssignmentQuestionNode']
    include: bool
    value: bool


AssignmentTree = dict[str, AssignmentQuestionNode]
# Question paths assigned to each leaf section, keyed by section id.
SectionQuestionPaths = dict[UUID, list[str]]


class SerializedSectionAssignment(TypedDict):
    id: str
    title: str
    assignments: AssignmentTree | None
    children: list['SerializedSectionAssignment'] | None


@dataclass
class SectionRecord:
    """A section in the template tree. Either a leaf or a parent (children set).

    `id` is a synthetic identifier minted when building section records and is unique across the tree.
    `title` is the human-readable label and may collide with sibling/cousin titles.
    """

    id: UUID
    title: str
    section: TemplateSection
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
    question_paths: list[str] | None = None  # leaf: matched question paths the assignments were expanded from

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
