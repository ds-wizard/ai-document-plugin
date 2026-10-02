export type TemplateScope = 'personal' | 'tenant'

export type TemplateOption = {
    uuid: string
    title: string
    scope: TemplateScope
}

export type LlmSettings = {
    model: string | null
    apiUrl: string | null
    maxWorkers: number | null
    apiKeySet: boolean
}

export type LlmSettingsUpdate = {
    model: string
    apiUrl: string
    /** Null keeps the API key that is already stored. */
    apiKey: string | null
    maxWorkers: number | null
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
    scope: TemplateScope
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

export type PipelineSummaryItem = {
    runId: string
    status: 'queued' | 'running' | 'succeeded' | 'failed'
    templateTitle: string
    error: PipelineErrorResponse | null
    progressMessage: string | null
    createdAt: string
    updatedAt: string
}

export type ResultRenderMode = 'formatted' | 'raw'
