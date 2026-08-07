from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _model_from_fields[T: ApiModel](
    model_type: type[T],
    **data: object,
) -> T:
    return model_type.model_validate(data)


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


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
    questionnaire_uuid: UUID = Field(alias='questionnaireUuid')
    template_uuid: UUID = Field(alias='templateUuid')
    llm_model: str = Field(alias='llmModel')
    llm_api_key: str = Field(alias='llmApiKey')
    llm_api_url: str = Field(alias='llmApiUrl')
    llm_max_workers: int | None = Field(default=None, alias='llmMaxWorkers', ge=1)


class PipelineSaveRequest(ApiModel):
    result_markdown: str = Field(alias='resultMarkdown')


class PipelineErrorResponse(ApiModel):
    type: ErrorType
    message: str


class PipelineSummaryResponse(ApiModel):
    run_id: UUID = Field(alias='runId')
    status: PipelineStatus
    title: str = Field(alias='templateTitle')
    error: PipelineErrorResponse | None = None
    progress_message: str | None = Field(default=None, alias='progressMessage')
    created_at: str = Field(alias='createdAt')
    updated_at: str = Field(alias='updatedAt')


class PipelineStatusResponse(ApiModel):
    run_id: UUID = Field(alias='runId')
    status: PipelineStatus
    questionnaire_uuid: UUID = Field(alias='questionnaireUuid')
    knowledge_model_uuid: UUID | None = Field(default=None, alias='knowledgeModelUuid')
    template_uuid: UUID = Field(alias='templateUuid')
    title: str = Field(alias='templateTitle')
    error: PipelineErrorResponse | None = None
    result_format: str | None = Field(default=None, alias='resultFormat')
    result_markdown: str | None = Field(default=None, alias='resultMarkdown')
    progress_message: str | None = Field(default=None, alias='progressMessage')
    updated_at: str = Field(alias='updatedAt')
