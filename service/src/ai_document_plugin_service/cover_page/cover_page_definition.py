from typing import Literal

from pydantic import BaseModel

from ai_document_plugin_service.ai.common.types import TemplateSection


class CoverPageLabel(BaseModel):
    id: str
    text: str


class CoverPageField(BaseModel):
    id: str
    label: str


class CoverPageMetadataField(CoverPageField):
    resolver: str
    preview: str


class CoverPageMetadata(BaseModel):
    title: CoverPageLabel
    columns: list[CoverPageLabel]
    fields: list[CoverPageMetadataField]
    attribution: str


class CoverPageHistoryColumn(CoverPageLabel):
    value_key: str
    formatter: Literal['text', 'date'] = 'text'


class CoverPageHistory(BaseModel):
    id: str
    title: CoverPageLabel
    resolver: str
    columns: list[CoverPageHistoryColumn]
    preview: str


class CoverPageSection(TemplateSection):
    id: str
    preview: str
    fields: list[CoverPageField]


class CoverPageDefinition(BaseModel):
    version: str
    metadata: CoverPageMetadata
    history: CoverPageHistory
    sections: list[CoverPageSection]


def cover_page_assignment_field_labels(definition: CoverPageDefinition) -> dict[str, str]:
    return {field.id: field.label for section in definition.sections for field in section.fields}
