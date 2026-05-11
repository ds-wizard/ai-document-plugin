export type TemplateOption = {
    uuid: string
    title: string
    source?: 'database' | 'local'
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
    templateUuid: string
    templateTitle: string
    error: string | null
    resultFormat: string | null
    resultMarkdown: string | null
    updatedAt: string
}

export type ResultRenderMode = 'formatted' | 'raw'
