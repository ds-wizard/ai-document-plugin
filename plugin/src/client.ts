import type {
    ApiErrorDetail,
    ApiTemplateContent,
    PipelineRunResponse,
    PipelineStatusResponse,
    TemplateDetail,
    TemplateOption,
} from '@/types'

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

function apiErrorMessage(data: ApiErrorDetail, fallback: string): string {
    return data.detail ?? fallback
}

async function fetchApi<T>(url: string, init: RequestInit | undefined, errorMessage: string): Promise<T> {
    const response = await fetch(url, init)
    const data = await readApiResponse<T | ApiErrorDetail>(response, url)

    if (!response.ok) {
        throw new Error(apiErrorMessage(data as ApiErrorDetail, errorMessage))
    }

    return data as T
}

export const getApiBaseUrl = (): string => __API_URL__.replace(/\/+$/, '')

export const getTemplates = async (): Promise<TemplateOption[]> => {
    const url = `${getApiBaseUrl()}/templates`
    return fetchApi<TemplateOption[]>(url, undefined, 'Failed to load the list of templates.')
}

export const getTemplate = async (templateUuid: string): Promise<TemplateDetail> => {
    const url = `${getApiBaseUrl()}/templates/${encodeURIComponent(templateUuid)}`
    return fetchApi<TemplateDetail>(url, undefined, 'Failed to load template.')
}

export const getPipelineStatus = async (runId: string): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}`
    return fetchApi<PipelineStatusResponse>(url, undefined, 'Failed to retrieve pipeline status.')
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
    return fetchApi<PipelineRunResponse>(
        url,
        {
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
        },
        'Pipeline execution failed.',
    )
}

type CreateTemplateParams = {
    title: string
    content: ApiTemplateContent
}

export const createTemplate = async ({
    title,
    content,
}: CreateTemplateParams): Promise<TemplateOption> => {
    const url = `${getApiBaseUrl()}/templates`
    return fetchApi<TemplateOption>(
        url,
        {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title,
                content,
            }),
        },
        'Failed to save template.',
    )
}

export const saveEditedPipelineResult = async (
    runId: string,
    resultMarkdown: string,
): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}/save`
    return fetchApi<PipelineStatusResponse>(
        url,
        {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                resultMarkdown,
            }),
        },
        'Failed to save the edited version.',
    )
}
