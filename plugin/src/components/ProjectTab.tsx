import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { useEffect, useState } from 'react'

import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'

type TemplateOption = {
    uuid: string
    title: string
}

type PipelineRunResponse = {
    status: string
    runId: string
    questionnaireUuid: string
    templateUuid: string
    templateTitle: string
}

type PipelineStatusResponse = {
    runId: string
    status: 'running' | 'succeeded' | 'failed'
    questionnaireUuid: string
    templateUuid: string
    templateTitle: string
    error: string | null
    updatedAt: string
}

const isPipelineStatusResponse = (value: unknown): value is PipelineStatusResponse => {
    if (!value || typeof value !== 'object') {
        return false
    }

    return 'runId' in value && 'status' in value && 'templateTitle' in value
}

const readApiResponse = async <T,>(response: Response, url: string): Promise<T> => {
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

export default function ProjectTab({
    settings: _settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const [templates, setTemplates] = useState<TemplateOption[]>([])
    const [selectedTemplateUuid, setSelectedTemplateUuid] = useState('')
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(true)
    const [isRunningPipeline, setIsRunningPipeline] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [infoMessage, setInfoMessage] = useState<string | null>(null)
    const [activeRunId, setActiveRunId] = useState<string | null>(null)

    useEffect(() => {
        let isMounted = true

        const loadTemplates = async () => {
            setIsLoadingTemplates(true)
            setErrorMessage(null)

            try {
                const url = `${__API_URL__}/templates`
                const response = await fetch(url)
                const data = await readApiResponse<TemplateOption[]>(response, url)

                if (!response.ok) {
                    throw new Error(`Failed to load the list of templates (${response.status}).`)
                }
                if (!isMounted) {
                    return
                }

                setTemplates(data)
                setSelectedTemplateUuid((currentValue) => currentValue || data[0]?.uuid || '')
            } catch (error) {
                if (!isMounted) {
                    return
                }

                const message =
                    error instanceof Error ? error.message : 'Nepodarilo se nacist seznam sablon.'
                setErrorMessage(message)
            } finally {
                if (isMounted) {
                    setIsLoadingTemplates(false)
                }
            }
        }

        void loadTemplates()

        return () => {
            isMounted = false
        }
    }, [])

    useEffect(() => {
        if (!activeRunId) {
            return
        }

        const pollStatus = async () => {
            try {
                const url = `${__API_URL__}/pipelines/status/${activeRunId}`
                const response = await fetch(url)
                const data = await readApiResponse<PipelineStatusResponse | { detail?: string }>(
                    response,
                    url,
                )

                if (!response.ok) {
                    throw new Error(
                        'detail' in data && data.detail
                            ? data.detail
                            : 'Failed to retrieve pipeline status.',
                    )
                }

                if (!isPipelineStatusResponse(data)) {
                    throw new Error('Invalid pipeline status returned.')
                }

                if (data.status === 'running') {
                    setInfoMessage(`Pipeline is running for the template "${data.templateTitle}".`)
                    return
                }

                setActiveRunId(null)
                setIsRunningPipeline(false)
                setInfoMessage(null)

                if (data.status === 'succeeded') {
                    setSuccessMessage(
                        `Pipeline has been completed for the template "${data.templateTitle}".`,
                    )
                    setErrorMessage(null)
                    return
                }

                setSuccessMessage(null)
                setErrorMessage(
                    data.error
                        ? `Pipeline failed: ${data.error}`
                        : `Pipeline failed for the template "${data.templateTitle}".`,
                )
            } catch (error) {
                setActiveRunId(null)
                setIsRunningPipeline(false)
                setSuccessMessage(null)
                setInfoMessage(null)
                setErrorMessage(
                    error instanceof Error ? error.message : 'Unable to determine pipeline status.',
                )
            }
        }

        void pollStatus()
        const intervalId = window.setInterval(() => {
            void pollStatus()
        }, 2000)

        return () => {
            window.clearInterval(intervalId)
        }
    }, [activeRunId])

    const handleRunPipeline = async () => {
        if (!project) {
            setErrorMessage('Project is not available.')
            return
        }

        if (!selectedTemplateUuid) {
            setErrorMessage('Select a DMP template.')
            return
        }

        setIsRunningPipeline(true)
        setErrorMessage(null)
        setSuccessMessage(null)
        setInfoMessage(null)

        try {
            const { apiUrl, token } = getApiUrlAndToken()
            if (!token) {
                throw new Error('Failed to retrieve the current user\'s authentication token.')
            }

            const url = `${__API_URL__}/pipelines/run`
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    questionnaireUuid: project.uuid,
                    templateUuid: selectedTemplateUuid,
                    token,
                    apiUrl,
                }),
            })

            const data = await readApiResponse<PipelineRunResponse | { detail?: string }>(
                response,
                url,
            )

            if (!response.ok) {
                throw new Error(
                    'detail' in data && data.detail ? data.detail : 'Pipeline execution failed..',
                )
            }

            if (!('runId' in data)) {
                throw new Error('The backend did not return a pipeline run identifier.')
            }

            setActiveRunId(data.runId)
            setInfoMessage(`Pipeline has been accepted for the template "${data.templateTitle}".`)
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Pipeline execution failed.'
            setErrorMessage(message)
            setIsRunningPipeline(false)
        }
    }

    return (
        <div
            style={{
                padding: '1.5rem',
                maxWidth: '42rem',
                margin: '0 auto',
                display: 'grid',
                gap: '1rem',
            }}
        >
            <div>
                <h1 style={{ margin: 0 }}>AI Document Generation</h1>
                <p style={{ margin: '0.5rem 0 0', color: '#475569' }}>
                    Select a DMP template from the database and run the pipeline on the current
                    project.
                </p>
            </div>

            {!project ? (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem',
                        background: '#fff7ed',
                        color: '#c2410c',
                    }}
                >
                    The project is not loaded; the pipeline cannot be started yet.
                </div>
            ) : null}

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>DMP template</span>
                <select
                    value={selectedTemplateUuid}
                    onChange={(event) => setSelectedTemplateUuid(event.target.value)}
                    disabled={
                        isLoadingTemplates ||
                        isRunningPipeline ||
                        templates.length === 0 ||
                        !project
                    }
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                >
                    {templates.length === 0 ? (
                        <option value="">
                            {isLoadingTemplates
                                ? 'Loading templates...'
                                : errorMessage
                                  ? 'Unable to load templates.'
                                  : 'No templates available.'}
                        </option>
                    ) : (
                        templates.map((template) => (
                            <option key={template.uuid} value={template.uuid}>
                                {template.title}
                            </option>
                        ))
                    )}
                </select>
            </label>

            <button
                type="button"
                onClick={() => void handleRunPipeline()}
                disabled={
                    isLoadingTemplates || isRunningPipeline || !selectedTemplateUuid || !project
                }
                style={{
                    width: 'fit-content',
                    padding: '0.8rem 1.2rem',
                    border: 0,
                    borderRadius: '999px',
                    background:
                        isLoadingTemplates || isRunningPipeline || !selectedTemplateUuid || !project
                            ? '#94a3b8'
                            : '#0f172a',
                    color: '#fff',
                    cursor:
                        isLoadingTemplates || isRunningPipeline || !selectedTemplateUuid || !project
                            ? 'not-allowed'
                            : 'pointer',
                    fontWeight: 600,
                }}
            >
                {isRunningPipeline ? 'Running pipeline...' : 'Run pipeline'}
            </button>

            {project ? (
                <div style={{ color: '#475569', fontSize: '0.95rem' }}>
                    Project: <strong>{project.name}</strong>
                </div>
            ) : null}

            {errorMessage ? (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem',
                        background: '#fef2f2',
                        color: '#b91c1c',
                    }}
                >
                    {errorMessage}
                </div>
            ) : null}

            {infoMessage ? (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem',
                        background: '#eff6ff',
                        color: '#1d4ed8',
                    }}
                >
                    {infoMessage}
                </div>
            ) : null}

            {successMessage ? (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem',
                        background: '#ecfdf5',
                        color: '#047857',
                    }}
                >
                    {successMessage}
                </div>
            ) : null}
        </div>
    )
}
