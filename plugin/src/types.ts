export type TemplateOption = {
    uuid: string
    title: string
}

export type PipelineErrorResponse = {
    type: string
    message: string
}

export type ApiTemplateSection = {
    title: string
    content?: string
    sections?: ApiTemplateSection[]
}

export type ApiTemplateContent = {
    sections: ApiTemplateSection[]
}

export type TemplateDetail = {
    uuid: string
    title: string
    content: ApiTemplateContent
}

export type PipelineRunResponse = {
    status: string
    runId: string
    questionnaireUuid: string
    templateUuid: string
    templateTitle: string
}

export type PipelineStatusResponse = {
    runId: string
    status: 'queued' | 'running' | 'succeeded' | 'failed'
    questionnaireUuid: string
    knowledgeModelUuid: string
    userUuid: string
    tenantUuid: string
    templateUuid: string
    templateTitle: string
    error: PipelineErrorResponse | null
    resultFormat: string | null
    resultMarkdown: string | null
    progressMessage: string | null
    updatedAt: string
}

export type ResultRenderMode = 'formatted' | 'raw'
