from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        serialize_by_alias=True,
    )


class ErrorType(StrEnum):
    AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED'
    SERVER_ERROR = 'SERVER_ERROR'
    TEMPLATE_NOT_FOUND = 'TEMPLATE_NOT_FOUND'


class PipelineStatus(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class TemplateScope(StrEnum):
    PERSONAL = 'personal'
    TENANT = 'tenant'

    @staticmethod
    def for_user(user_uuid: UUID | None) -> 'TemplateScope':
        """A row with an owner is personal; without one it is tenant-wide."""
        return TemplateScope.PERSONAL if user_uuid is not None else TemplateScope.TENANT


class TemplateListItem(ApiModel):
    uuid: str
    title: str
    scope: TemplateScope


class TemplateDetail(ApiModel):
    uuid: UUID
    title: str
    content: dict
    scope: TemplateScope


class TemplateCreateRequest(ApiModel):
    title: str
    content: dict
    scope: TemplateScope = TemplateScope.PERSONAL


class TemplateUpdateRequest(ApiModel):
    title: str
    content: dict


class PipelineRunRequest(ApiModel):
    questionnaire_uuid: UUID
    template_uuid: UUID
    language: str = Field(default='en', min_length=2, max_length=10, pattern=r'^[a-z]{2,3}(?:-[A-Z]{2})?$')
    llm_model: str
    llm_api_key: str
    llm_api_url: str
    llm_max_workers: int | None = Field(default=None, ge=1)


class PipelineSaveRequest(ApiModel):
    result_markdown: str


class PipelineExportRequest(ApiModel):
    """Carries the editor's current text so unsaved edits can be exported."""

    result_markdown: str


class PipelineErrorResponse(ApiModel):
    type: ErrorType
    message: str


class PipelineSummaryResponse(ApiModel):
    run_id: UUID
    status: PipelineStatus
    template_title: str
    error: PipelineErrorResponse | None = None
    progress_message: str | None = None
    created_at: str
    updated_at: str


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
    progress_message: str | None = None
    updated_at: str
