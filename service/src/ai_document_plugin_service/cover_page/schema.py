from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TranslatableLabel(StrictModel):
    id: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    text: str = Field(min_length=1)


class MetadataFieldDefinition(StrictModel):
    id: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    label: str = Field(min_length=1)
    resolver: str = Field(min_length=1, pattern=r'^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$')
    preview: str = Field(min_length=1)


class MetadataSectionDefinition(StrictModel):
    title: TranslatableLabel
    columns: tuple[TranslatableLabel, TranslatableLabel]
    fields: list[MetadataFieldDefinition] = Field(min_length=1)
    attribution: str = Field(min_length=1)


class HistoryColumnDefinition(TranslatableLabel):
    value_key: str = Field(min_length=1)
    formatter: Literal['text', 'date'] = 'text'


class HistorySectionDefinition(StrictModel):
    id: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    title: TranslatableLabel
    resolver: str = Field(min_length=1, pattern=r'^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$')
    columns: list[HistoryColumnDefinition] = Field(min_length=1)
    preview: str = Field(min_length=1)


class AssignmentFieldDefinition(StrictModel):
    id: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    label: str = Field(min_length=1)
    required: bool = False


class AssignmentSectionDefinition(StrictModel):
    id: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    item_name: str = Field(min_length=1)
    item_heading_field: Identifier = Field(pattern=r'^[a-z][a-z0-9_]*$')
    preserve_item_headings: bool = True
    preview: str = Field(min_length=1)
    fields: list[AssignmentFieldDefinition] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_heading_field(self) -> AssignmentSectionDefinition:
        field_ids = [field.id for field in self.fields]
        if len(field_ids) != len(set(field_ids)):
            msg = f"Assigned section '{self.id}' contains duplicate field IDs"
            raise ValueError(msg)
        if self.item_heading_field not in field_ids:
            msg = f"Assigned section '{self.id}' references missing heading field '{self.item_heading_field}'"
            raise ValueError(msg)
        return self


class CoverPageDefinition(StrictModel):
    version: str = Field(min_length=1)
    metadata: MetadataSectionDefinition
    history: HistorySectionDefinition
    assigned_sections: list[AssignmentSectionDefinition] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_unique_ids(self) -> CoverPageDefinition:
        section_ids = [section.id for section in self.assigned_sections]
        block_ids = ['metadata', self.history.id, *section_ids]
        if len(block_ids) != len(set(block_ids)):
            msg = 'Cover definition contains duplicate block IDs'
            raise ValueError(msg)

        label_ids = [
            self.metadata.title.id,
            *(column.id for column in self.metadata.columns),
            *(field.id for field in self.metadata.fields),
            self.history.title.id,
            *(column.id for column in self.history.columns),
            *(field.id for section in self.assigned_sections for field in section.fields),
        ]
        if len(label_ids) != len(set(label_ids)):
            msg = 'Cover definition contains duplicate translatable label IDs'
            raise ValueError(msg)
        return self
