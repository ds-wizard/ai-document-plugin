import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'

import type {
    PipelineStatusResponse,
    PipelineSummaryItem,
    TemplateDetail,
    TemplateOption,
    TemplateScope,
} from '@/types'

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

const buildAuthHeaders = (): Record<string, string> => {
    const { apiUrl, token } = getApiUrlAndToken()
    if (!token) {
        throw new Error("Failed to retrieve the current user's authentication token.")
    }
    if (!apiUrl) {
        throw new Error('Failed to retrieve the DSW API URL.')
    }

    return {
        Authorization: `Bearer ${token}`,
        'X-Dsw-Api-Url': apiUrl,
    }
}

// false positive for global type RequestInit
// eslint-disable-next-line no-undef
const apiFetch = (url: string, init?: RequestInit): Promise<Response> =>
    fetch(url, {
        ...init,
        headers: {
            ...buildAuthHeaders(),
            ...init?.headers,
        },
    })

export const getTemplates = async (): Promise<TemplateOption[]> => {
    const url = `${getApiBaseUrl()}/templates`
    const response = await apiFetch(url)
    const templates = await readApiResponse<TemplateOption[]>(response, url)

    if (!response.ok) {
        throw new Error(`Failed to load the list of templates (${response.status}).`)
    }

    return templates
}

export const getTemplate = async (templateUuid: string): Promise<TemplateDetail> => {
    const url = `${getApiBaseUrl()}/templates/${encodeURIComponent(templateUuid)}`
    const response = await apiFetch(url)
    const data = await readApiResponse<TemplateDetail>(response, url)

    if (!response.ok) {
        throw new Error(`Failed to load template (${response.status}).`)
    }
    return data
}

export const getPipelineStatus = async (runId: string): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}`
    const response = await apiFetch(url)
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

export const getPipelineHistory = async (
    questionnaireUuid: string,
): Promise<PipelineSummaryItem[]> => {
    const url = `${getApiBaseUrl()}/pipelines?questionnaireUuid=${encodeURIComponent(questionnaireUuid)}`
    const response = await apiFetch(url)
    const data = await readApiResponse<PipelineSummaryItem[] | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail
                ? data.detail
                : 'Failed to load the generation history.',
        )
    }

    if (!Array.isArray(data)) {
        throw new Error('Invalid generation history returned.')
    }

    return data
}

type RunPipelineParams = {
    questionnaireUuid: string
    templateUuid: string
    llmModel?: string | null
    llmApiKey?: string | null
    llmApiUrl?: string | null
    llmMaxWorkers?: number | null
}

export const runPipeline = async ({
    questionnaireUuid,
    templateUuid,
    llmModel = null,
    llmApiKey = null,
    llmApiUrl = null,
    llmMaxWorkers = null,
}: RunPipelineParams): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/run`
    const response = await apiFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            questionnaireUuid,
            templateUuid,
            llmModel,
            llmApiKey,
            llmApiUrl,
            llmMaxWorkers,
        }),
    })

    const data = await readApiResponse<PipelineStatusResponse | { detail?: unknown }>(response, url)

    if (!response.ok) {
        if (response.status == 422) {
            throw new Error(
                'Plugin is not configured. Set the model, API key, and API URL in the plugin settings.',
            )
        }
        const detail = 'detail' in data ? data.detail : undefined
        throw new Error(
            typeof detail === 'string' && detail ? detail : 'Pipeline execution failed.',
        )
    }

    if (!isPipelineStatusResponse(data)) {
        throw new Error('The backend did not return a pipeline run identifier.')
    }

    return data
}

type CreateTemplateParams = {
    title: string
    content: unknown
    scope: TemplateScope
}

export const createTemplate = async ({
    title,
    content,
    scope,
}: CreateTemplateParams): Promise<TemplateDetail> => {
    const url = `${getApiBaseUrl()}/templates`
    const response = await apiFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            title,
            content,
            scope,
        }),
    })

    const data = await readApiResponse<TemplateDetail | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Failed to save the template.',
        )
    }

    if (!('uuid' in data) || !('title' in data) || !('content' in data)) {
        throw new Error('The backend did not return a saved template.')
    }

    return data
}

type UpdateTemplateParams = {
    uuid: string
    title: string
    content: unknown
}

export const updateTemplate = async ({
    uuid,
    title,
    content,
}: UpdateTemplateParams): Promise<TemplateDetail> => {
    const url = `${getApiBaseUrl()}/templates/${encodeURIComponent(uuid)}`
    const response = await apiFetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            title,
            content,
        }),
    })

    const data = await readApiResponse<TemplateDetail | { detail?: string }>(response, url)

    if (!response.ok) {
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Failed to update the template.',
        )
    }

    if (!('uuid' in data) || !('title' in data) || !('content' in data)) {
        throw new Error('The backend did not return the updated template.')
    }

    return data
}

export const deleteTemplate = async (templateUuid: string): Promise<void> => {
    const url = `${getApiBaseUrl()}/templates/${encodeURIComponent(templateUuid)}`
    const response = await apiFetch(url, { method: 'DELETE' })

    if (!response.ok) {
        const data = await readApiResponse<{ detail?: string }>(response, url).catch(() => ({}))
        throw new Error(
            'detail' in data && data.detail ? data.detail : 'Failed to delete the template.',
        )
    }
}

export const exportPipelineResultAsDocx = async (
    runId: string,
    resultMarkdown: string,
): Promise<Blob> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}/export/docx`
    const response = await apiFetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            resultMarkdown,
        }),
    })

    if (!response.ok) {
        // Errors still come back as JSON; only the success path is binary.
        const data = await readApiResponse<{ detail?: string }>(response, url).catch(
            (): { detail?: string } => ({}),
        )
        throw new Error(data.detail || 'Failed to export the result as a Word document.')
    }

    return response.blob()
}

export const saveEditedPipelineResult = async (
    runId: string,
    resultMarkdown: string,
): Promise<PipelineStatusResponse> => {
    const url = `${getApiBaseUrl()}/pipelines/status/${runId}/save`
    const response = await apiFetch(url, {
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
