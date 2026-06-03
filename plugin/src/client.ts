import type { PipelineRunResponse, PipelineStatusResponse, TemplateOption } from '@/types'

export const isPipelineStatusResponse = (value: unknown): value is PipelineStatusResponse => {
    if (!value || typeof value !== 'object') {
        return false
    }

    return 'runId' in value && 'status' in value && 'templateTitle' in value
}

export const readApiResponse = async <T>(response: Response, url: string): Promise<T> => {
    const responseText = await response.text()
    const contentType = response.headers.get('content-type') || ''

    if (!contentType.includes('application/json')) {
        const preview = responseText.slice(0, 120).trim()
        throw new Error(
            `Endpoint ${url} returned an unexpected response instead of JSON (${response.status} ${response.statusText}): ${preview}`,
        )
    }

    try {
        return JSON.parse(responseText) as T
    } catch {
        throw new Error(`Endpoint ${url} returned invalid JSON.`)
    }
}
// __API_URL__ (with removed trailing /. e.g.: example.com/ => example.com
export const getApiBaseUrl = (): string => __API_URL__.replace(/\/+$/, '')

export const getTemplates = async (): Promise<TemplateOption[]> => {
    const url = `${getApiBaseUrl()}/templates`
    const response = await fetch(url)
    const templates = await readApiResponse<TemplateOption[]>(response, url)

    if (!response.ok) {
        throw new Error(`Failed to load the list of templates (${response.status}).`)
    }

    return templates
}

export const getPipelineStatus = async (runId: string): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}`
    const response = await fetch(url)
    const data = await readApiResponse<PipelineStatusResponse | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Failed to retrieve pipeline status.',
        )
    }

    if (!isPipelineStatusResponse(data)) {
        throw new Error('Invalid pipeline status returned.')
    }

    return data
}

type RunPipelineParams = {
    questionnaireUuid: string
    templateUuid: string
    token: string
    apiUrl: string
    llmModel?: string | null
    llmApiKey?: string | null
    llmApiUrl?: string | null
    llmMaxWorkers?: number | null
}

export const runPipeline = async ({
    questionnaireUuid,
    templateUuid,
    token,
    apiUrl,
    llmModel = null,
    llmApiKey = null,
    llmApiUrl = null,
    llmMaxWorkers = null,
}: RunPipelineParams): Promise<PipelineRunResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/run`
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            questionnaireUuid,
            templateUuid,
            token,
            apiUrl,
            llmModel,
            llmApiKey,
            llmApiUrl,
            llmMaxWorkers,
        }),
    })

    const data = await readApiResponse<PipelineRunResponse | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Pipeline execution failed.',
        )
    }

    if (!('runId' in data)) {
        throw new Error('The backend did not return a pipeline run identifier.')
    }

    return data
}

type CreateTemplateParams = {
    title: string
    content: unknown
}

export const createTemplate = async ({
    title,
    content,
}: CreateTemplateParams): Promise<TemplateOption> => {
    const url = `${getApiBaseUrl()}/templates`
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            title,
            content,
        }),
    })

    const data = await readApiResponse<TemplateOption | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Pipeline execution failed.',
        )
    }

    if (!('uuid' in data) || !('title' in data)) {
        throw new Error('The backend did not return a saved template.')
    }

    return data
}

export const saveEditedPipelineResult = async (
    runId: string,
    resultMarkdown: string,
): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}/save`
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            resultMarkdown,
        }),
    })

    const data = await readApiResponse<PipelineStatusResponse | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Failed to save the edited version.',
        )
    }

    if (!isPipelineStatusResponse(data)) {
        throw new Error('Invalid pipeline status returned after save.')
    }

    return data
}
