from pydantic import BaseModel, ConfigDict, Field


def _model_from_fields[T: ApiModel](
    model_type: type[T],
    **data: object,
) -> T:
    return model_type.model_validate(data)


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class TemplateListItem(ApiModel):
    uuid: str
    title: str


class TemplateCreateRequest(ApiModel):
    title: str
    content: dict


class PipelineRunRequest(ApiModel):
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    template_uuid: str = Field(alias='templateUuid')
    token: str
    api_url: str | None = Field(default=None, alias='apiUrl')
    llm_model: str | None = Field(default=None, alias='llmModel')
    llm_api_key: str | None = Field(default=None, alias='llmApiKey')
    llm_api_url: str | None = Field(default=None, alias='llmApiUrl')


class PipelineRunResponse(ApiModel):
    status: str
    run_id: str = Field(alias='runId')
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    template_uuid: str = Field(alias='templateUuid')
    template_title: str = Field(alias='templateTitle')


class PipelineSaveRequest(ApiModel):
    result_markdown: str = Field(alias='resultMarkdown')


class PipelineStatusResponse(ApiModel):
    run_id: str = Field(alias='runId')
    status: str
    questionnaire_uuid: str = Field(alias='questionnaireUuid')
    knowledge_model_uuid: str | None = Field(default=None, alias='knowledgeModelUuid')
    template_uuid: str = Field(alias='templateUuid')
    template_title: str = Field(alias='templateTitle')
    error: str | None = None
    result_format: str | None = Field(default=None, alias='resultFormat')
    result_markdown: str | None = Field(default=None, alias='resultMarkdown')
    updated_at: str = Field(alias='updatedAt')
