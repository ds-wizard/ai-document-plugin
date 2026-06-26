from enum import StrEnum

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
    ACCEPTED = 'accepted'
    QUEUED = 'queued'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class TemplateListItem(ApiModel):
    uuid: str
    title: str


class TemplateDetail(ApiModel):
    uuid: str
    title: str
    content: dict


class TemplateCreateRequest(ApiModel):
    title: str
    content: dict


class PipelineRunRequest(ApiModel):
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    template_uuid: str = Field(alias='templateUuid')
    llm_model: str = Field(alias='llmModel')
    llm_api_key: str = Field(alias='llmApiKey')
    llm_api_url: str = Field(alias='llmApiUrl')
    llm_max_workers: int | None = Field(default=None, alias='llmMaxWorkers', ge=1)


class PipelineRunResponse(ApiModel):
    status: PipelineStatus
    run_id: str = Field(alias='runId')
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    template_uuid: str = Field(alias='templateUuid')
    template_title: str = Field(alias='templateTitle')


class PipelineSaveRequest(ApiModel):
    result_markdown: str = Field(alias='resultMarkdown')


class PipelineErrorResponse(ApiModel):
    type: ErrorType
    message: str


class PipelineStatusResponse(ApiModel):
    run_id: str = Field(alias='runId')
    status: PipelineStatus
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    knowledge_model_uuid: str | None = Field(default=None, alias='knowledgeModelUuid')
    user_uuid: str = Field(alias='userUuid')
    tenant_uuid: str = Field(alias='tenantUuid')
    template_uuid: str = Field(alias='templateUuid')
    template_title: str = Field(alias='templateTitle')
    error: PipelineErrorResponse | None = None
    result_format: str | None = Field(default=None, alias='resultFormat')
    result_markdown: str | None = Field(default=None, alias='resultMarkdown')
    progress_message: str | None = Field(default=None, alias='progressMessage')
    updated_at: str = Field(alias='updatedAt')
