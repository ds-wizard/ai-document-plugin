import { pluginMetadata } from '@/metadata'
import type { PipelineRunResponse, PipelineStatusResponse, TemplateOption } from '@/types'

const AUTHORIZATION_ERROR_MESSAGE = 'Authorization error, invalid or expired token.'
const INTERNAL_SERVER_ERROR_MESSAGE = 'The action could not be completed. Please try again later.'

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

const getApiFailureMessage = (statusCode: number): string =>
    statusCode === 401 ? AUTHORIZATION_ERROR_MESSAGE : INTERNAL_SERVER_ERROR_MESSAGE

const isAuthorizationErrorPayload = (data: unknown): boolean => {
    if (!data || typeof data !== 'object') {
        return false
    }

    if (isPipelineStatusResponse(data) && typeof data.error === 'string') {
        const normalizedError = data.error.toLowerCase()
        return (
            normalizedError.includes('authentication error') ||
            normalizedError.includes('invalid proxy server token') ||
            normalizedError.includes('token_not_found_in_db') ||
            normalizedError.includes('error code: 401') ||
            normalizedError.startsWith('401 ')
        )
    }

    if ('detail' in data && typeof data.detail === 'string') {
        const normalizedDetail = data.detail.toLowerCase()
        return normalizedDetail.includes('401') || normalizedDetail.includes('token')
    }

    return false
}

const normalizeBaseUrl = (value: string): string => value.replace(/\/+$/, '')

const buildApiBaseCandidates = (serviceUrl: string | undefined): string[] => {
    const explicitServiceUrl = serviceUrl?.trim()
    const candidates = [
        explicitServiceUrl || null,
        __API_URL__,
        `${__API_URL__}/api`,
        __API_URL__.includes('/plugins/')
            ? __API_URL__.replace('/plugins/', '/plugin-services/')
            : null,
        __API_URL__.includes('/plugins/') ? __API_URL__.replace('/plugins/', '/services/') : null,
        `${window.location.origin}/gateway/plugin-services/${pluginMetadata.uuid}`,
        `${window.location.origin}/gateway/services/${pluginMetadata.uuid}`,
        `${window.location.origin}/gateway/plugin-service/${pluginMetadata.uuid}`,
        `${window.location.origin}/gateway/${pluginMetadata.uuid}`,
    ]

    return [
        ...new Set(
            candidates
                .filter((candidate): candidate is string => Boolean(candidate))
                .map(normalizeBaseUrl),
        ),
    ]
}

export const discoverApiBase = async (serviceUrl: string | undefined): Promise<string> => {
    const candidates = buildApiBaseCandidates(serviceUrl)

    for (const candidate of candidates) {
        try {
            const response = await fetch(`${candidate}/health`)
            const data = await readApiResponse<{ status?: string }>(response, `${candidate}/health`)

            if (response.ok && data.status === 'healthy') {
                return candidate
            }
        } catch {
            continue
        }
    }

    throw new Error(`Unable to locate plugin backend. Tried: ${candidates.join(', ')}`)
}

export const getTemplates = async (
    serviceUrl: string | undefined,
): Promise<{ baseUrl: string; templates: TemplateOption[] }> => {
    const baseUrl = await discoverApiBase(serviceUrl)
    const url = `${baseUrl}/templates`
    const response = await fetch(url)
    const templates = await readApiResponse<TemplateOption[]>(response, url)

    if (!response.ok) {
        throw new Error(getApiFailureMessage(response.status))
    }

    return { baseUrl, templates }
}

export const getPipelineStatus = async (
    apiBaseUrl: string,
    runId: string,
): Promise<PipelineStatusResponse> => {
    const url = `${apiBaseUrl}/pipelines/status/${runId}`
    const response = await fetch(url)
    const data = await readApiResponse<PipelineStatusResponse | { detail?: string }>(response, url)

    if (!response.ok) {
        if (isAuthorizationErrorPayload(data)) {
            throw new Error(AUTHORIZATION_ERROR_MESSAGE)
        }
        throw new Error(getApiFailureMessage(response.status))
    }

    if (!isPipelineStatusResponse(data)) {
        throw new Error('Invalid pipeline status returned.')
    }

    return data
}

type RunPipelineParams = {
    apiBaseUrl: string
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
    apiBaseUrl,
    questionnaireUuid,
    templateUuid,
    token,
    apiUrl,
    llmModel = null,
    llmApiKey = null,
    llmApiUrl = null,
    llmMaxWorkers = null,
}: RunPipelineParams): Promise<PipelineRunResponse> => {
    const url = `${apiBaseUrl}/pipelines/run`
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
        throw new Error(getApiFailureMessage(response.status))
    }

    if (!('runId' in data)) {
        throw new Error('The backend did not return a pipeline run identifier.')
    }

    return data
}

type CreateTemplateParams = {
    apiBaseUrl: string
    title: string
    content: unknown
}

export const createTemplate = async ({
    apiBaseUrl,
    title,
    content,
}: CreateTemplateParams): Promise<TemplateOption> => {
    const url = `${apiBaseUrl}/templates`
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
        throw new Error(getApiFailureMessage(response.status))
    }

    if (!('uuid' in data) || !('title' in data)) {
        throw new Error('The backend did not return a saved template.')
    }

    return data
}

export const saveEditedPipelineResult = async (
    apiBaseUrl: string,
    runId: string,
    resultMarkdown: string,
): Promise<PipelineStatusResponse> => {
    const url = `${apiBaseUrl}/pipelines/status/${runId}/save`
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
        throw new Error(getApiFailureMessage(response.status))
    }

    if (!isPipelineStatusResponse(data)) {
        throw new Error('Invalid pipeline status returned after save.')
    }

    return data
}
