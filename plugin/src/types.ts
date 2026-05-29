export type TemplateOption = {
    uuid: string
    title: string
    source?: 'database' | 'local'
}

export type PipelineErrorResponse = {
    type: string
    message: string
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
    status: 'running' | 'succeeded' | 'failed'
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
