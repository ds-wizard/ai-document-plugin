from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

from ai_document_plugin_service.ai.common.types import TemplateContent
from ai_document_plugin_service.data.languages import get_translation

if TYPE_CHECKING:
    from ai_document_plugin_service.cover_page.cover_page_definition import CoverPageDefinition

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ApiModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class ErrorType(StrEnum):
    """
    Error of a pipeline run, each type carries the message shown to the user.

    Note: The values are stored in the DB. Changing them requires a migration.
    """

    LLM_AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED'
    LLM_CONNECTION_FAILED = 'LLM_CONNECTION_FAILED'
    LLM_NOT_FOUND = 'LLM_NOT_FOUND'
    LLM_RATE_LIMITED = 'LLM_RATE_LIMITED'
    LLM_GENERAL_ERROR = 'LLM_GENERAL_ERROR'
    LLM_UNAVAILABLE = 'LLM_UNAVAILABLE'
    SERVER_ERROR = 'SERVER_ERROR'
    TEMPLATE_NOT_FOUND = 'TEMPLATE_NOT_FOUND'

    @property
    def message(self) -> str:
        return _ERROR_MESSAGES[self]


_ERROR_MESSAGES = {
    ErrorType.LLM_AUTHENTICATION_FAILED: (
        'The AI provider rejected the API token. Check the token in the AI configuration.'
    ),
    ErrorType.LLM_CONNECTION_FAILED: (
        'The AI provider could not be reached. Check the API URL in the AI configuration or try again later.'
    ),
    ErrorType.LLM_NOT_FOUND: (
        'The AI provider did not find the configured model or endpoint. Check the model name and API URL '
        'in the AI configuration.'
    ),
    ErrorType.LLM_RATE_LIMITED: (
        'The rate limit of the AI provider was reached. Decrease the maximum parallel requests in the plugin settings.'
    ),
    ErrorType.LLM_GENERAL_ERROR: (
        'The AI provider request failed. Verify the plugin configuration, it should be OpenAI compatible API.'
    ),
    ErrorType.LLM_UNAVAILABLE: 'The AI provider is currently unavailable. Please try again later.',
    ErrorType.SERVER_ERROR: 'The action could not be completed. Please try again later.',
    ErrorType.TEMPLATE_NOT_FOUND: 'Template not found.',
}


class PipelineStatus(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class TemplateScope(StrEnum):
    PERSONAL = 'personal'
    TENANT = 'tenant'

    @staticmethod
    def for_user(user_uuid: UUID | None) -> 'TemplateScope':
        """A row with an owner is personal; without one it is tenant-wide."""
        return TemplateScope.PERSONAL if user_uuid is not None else TemplateScope.TENANT


class TemplateListItem(ApiModel):
    has_cover_page: bool = False
    uuid: UUID
    title: str
    scope: TemplateScope


class TemplateDetail(ApiModel):
    has_cover_page: bool = False
    uuid: UUID
    title: str
    content: TemplateContent
    scope: TemplateScope


class TemplateCreateRequest(ApiModel):
    has_cover_page: bool = False
    title: str
    content: TemplateContent
    scope: TemplateScope = TemplateScope.PERSONAL


class TemplateUpdateRequest(ApiModel):
    has_cover_page: bool = False
    title: str
    content: TemplateContent


class QuestionnaireLanguageResponse(ApiModel):
    language: str | None


class LanguageOptionResponse(ApiModel):
    code: str
    name: str
    native_name: str


class CoverPagePreviewLabel(ApiModel):
    id: str
    text: str


class CoverPagePreviewField(ApiModel):
    id: str
    label: str
    preview: str


class CoverPagePreviewMetadata(ApiModel):
    title: CoverPagePreviewLabel
    columns: list[CoverPagePreviewLabel]
    fields: list[CoverPagePreviewField]
    attribution: str


class CoverPagePreviewHistory(ApiModel):
    id: str
    title: CoverPagePreviewLabel
    columns: list[CoverPagePreviewLabel]
    preview: str


class CoverPagePreviewAssignmentField(ApiModel):
    id: str
    label: str


class CoverPagePreviewAssignmentSection(ApiModel):
    id: str
    title: str
    preview: str
    fields: list[CoverPagePreviewAssignmentField]


class CoverPagePreviewDefinition(ApiModel):
    version: str
    metadata: CoverPagePreviewMetadata
    history: CoverPagePreviewHistory
    assigned_sections: list[CoverPagePreviewAssignmentSection]

    @classmethod
    def from_definition(cls, definition: 'CoverPageDefinition') -> Self:
        metadata = definition.metadata
        history = definition.history
        return cls(
            version=definition.version,
            metadata=CoverPagePreviewMetadata(
                title=CoverPagePreviewLabel(
                    id=metadata.title.id,
                    text=metadata.title.text,
                ),
                columns=[CoverPagePreviewLabel(id=column.id, text=column.text) for column in metadata.columns],
                fields=[
                    CoverPagePreviewField(id=field.id, label=field.label, preview=field.preview)
                    for field in metadata.fields
                ],
                attribution=metadata.attribution,
            ),
            history=CoverPagePreviewHistory(
                id=history.id,
                title=CoverPagePreviewLabel(
                    id=history.title.id,
                    text=history.title.text,
                ),
                columns=[CoverPagePreviewLabel(id=column.id, text=column.text) for column in history.columns],
                preview=history.preview,
            ),
            assigned_sections=[
                CoverPagePreviewAssignmentSection(
                    id=section.id,
                    title=section.title,
                    preview=section.preview,
                    fields=[
                        CoverPagePreviewAssignmentField(id=field.id, label=field.label) for field in section.fields
                    ],
                )
                for section in definition.sections
            ],
        )


class PipelineRunRequest(ApiModel):
    time_zone: str = 'UTC'
    questionnaire_uuid: UUID
    template_uuid: UUID
    language: str = Field(
        default='en', validate_default=True, min_length=2, max_length=10, pattern=r'^[a-z]{2,3}(?:-[A-Z]{2})?$'
    )

    @field_validator('language')
    @classmethod
    def validate_language(cls, value: str) -> str:
        get_translation(value)
        return value

    @field_validator('time_zone')
    @classmethod
    def validate_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            msg = 'Unknown time zone.'
            raise ValueError(msg) from error
        return value


class LlmSettingsResponse(ApiModel):
    """The tenant's LLM settings. The API key itself is never returned."""

    model: str | None
    api_url: str | None
    max_workers: int | None
    api_key_set: bool


class LlmSettingsUpdateRequest(ApiModel):
    model: NonEmptyStr
    api_url: NonEmptyStr
    # Omitted keeps the API key that is already stored.
    api_key: NonEmptyStr | None = None
    max_workers: int | None = Field(default=None, ge=1)


class PipelineSaveRequest(ApiModel):
    result_markdown: str


class PipelineRenameRequest(ApiModel):
    title: NonEmptyStr


class PipelineExportRequest(ApiModel):
    """Carries the editor's current text so unsaved edits can be exported."""

    result_markdown: str


class PipelineErrorResponse(ApiModel):
    type: ErrorType
    message: str


class QuestionnaireValueChangeResponse(ApiModel):
    """A reply that differs between the generation and the questionnaire now."""

    kind: Literal['added', 'changed', 'removed']
    old_value: str | None = None
    new_value: str | None = None


class QuestionnaireChangeNodeResponse(ApiModel):
    """A chapter, question or list item with changes in it, in the questionnaire's order."""

    path: str
    kind: Literal['chapter', 'question', 'item']
    title: str | None = None
    # The change of this node's own reply, if it changed.
    change: QuestionnaireValueChangeResponse | None = None
    # The selected answer of an options question that did not change itself but has changed follow-ups.
    answer: str | None = None
    children: list['QuestionnaireChangeNodeResponse']


class QuestionnaireChangesResponse(ApiModel):
    # False for generations that did not store their replies, so there is nothing to compare with.
    available: bool
    tree: list[QuestionnaireChangeNodeResponse]


class PipelineSummaryResponse(ApiModel):
    run_id: UUID
    template_uuid: UUID
    status: PipelineStatus
    template_title: str
    error: PipelineErrorResponse | None = None
    progress_message: str | None = None
    created_at: str
    updated_at: str
    named_version: str | None = None
    # Newest DSW questionnaire event when the run read the answers; None for older runs.
    source_event_uuid: UUID | None = None


class PipelineStatusResponse(ApiModel):
    run_id: UUID
    status: PipelineStatus
    questionnaire_uuid: UUID
    knowledge_model_uuid: UUID | None = None
    template_uuid: UUID
    template_title: str
    error: PipelineErrorResponse | None = None
    result_format: str | None = None
    result_markdown: str | None = None
    created_at: str
    progress_message: str | None = None
    updated_at: str
    named_version: str | None = None
    source_event_uuid: UUID | None = None
