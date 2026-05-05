import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { Fragment, ReactNode, useEffect, useState } from 'react'

import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import { pluginMetadata } from '@/metadata'

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
    resultFormat: string | null
    resultMarkdown: string | null
    updatedAt: string
}

type ResultRenderMode = 'formatted' | 'raw'

const isPipelineStatusResponse = (value: unknown): value is PipelineStatusResponse => {
    if (!value || typeof value !== 'object') {
        return false
    }

    return 'runId' in value && 'status' in value && 'templateTitle' in value
}

const formatInlineMarkdown = (text: string): ReactNode[] => {
    const pattern = /(\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*)/g
    const parts: ReactNode[] = []
    let lastIndex = 0

    for (const match of text.matchAll(pattern)) {
        const fullMatch = match[0]
        const index = match.index ?? 0

        if (index > lastIndex) {
            parts.push(text.slice(lastIndex, index))
        }

        if (match[2] && match[3]) {
            parts.push(
                <a
                    key={`${index}-${fullMatch}`}
                    href={match[3]}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#1d4ed8' }}
                >
                    {match[2]}
                </a>,
            )
        } else if (match[4]) {
            parts.push(
                <code
                    key={`${index}-${fullMatch}`}
                    style={{
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        background: '#e2e8f0',
                        borderRadius: '0.25rem',
                        padding: '0.1rem 0.3rem',
                    }}
                >
                    {match[4]}
                </code>,
            )
        } else if (match[5]) {
            parts.push(<strong key={`${index}-${fullMatch}`}>{match[5]}</strong>)
        } else if (match[6]) {
            parts.push(<em key={`${index}-${fullMatch}`}>{match[6]}</em>)
        }

        lastIndex = index + fullMatch.length
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex))
    }

    return parts.length > 0 ? parts : [text]
}

const renderMarkdownBlocks = (markdown: string): ReactNode[] => {
    const lines = markdown.replace(/\r\n/g, '\n').split('\n')
    const blocks: ReactNode[] = []
    let index = 0

    const isTableSeparatorLine = (value: string): boolean => {
        const cells = value
            .trim()
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((cell) => cell.trim())

        return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
    }

    const parseTableRow = (value: string): string[] =>
        value
            .trim()
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((cell) => cell.trim())

    while (index < lines.length) {
        const line = lines[index]
        const trimmed = line.trim()

        if (!trimmed) {
            index += 1
            continue
        }

        if (trimmed.startsWith('```')) {
            const codeLines: string[] = []
            index += 1

            while (index < lines.length && !lines[index].trim().startsWith('```')) {
                codeLines.push(lines[index])
                index += 1
            }

            if (index < lines.length) {
                index += 1
            }

            blocks.push(
                <pre
                    key={`code-${blocks.length}`}
                    style={{
                        margin: 0,
                        padding: '1rem',
                        borderRadius: '0.75rem',
                        background: '#0f172a',
                        color: '#e2e8f0',
                        overflowX: 'auto',
                    }}
                >
                    <code>{codeLines.join('\n')}</code>
                </pre>,
            )
            continue
        }

        if (/^#{1,6}\s+/.test(trimmed)) {
            const level = Math.min(trimmed.match(/^#+/)?.[0].length ?? 1, 6)
            const content = trimmed.replace(/^#{1,6}\s+/, '')
            const fontSizes = ['2rem', '1.65rem', '1.35rem', '1.15rem', '1rem', '0.95rem']
            blocks.push(
                <div
                    key={`heading-${blocks.length}`}
                    style={{
                        fontSize: fontSizes[level - 1],
                        fontWeight: 700,
                        lineHeight: 1.2,
                        marginTop: blocks.length === 0 ? 0 : '0.5rem',
                    }}
                >
                    {formatInlineMarkdown(content)}
                </div>,
            )
            index += 1
            continue
        }

        if (/^(-|\*)\s+/.test(trimmed)) {
            const items: string[] = []

            while (index < lines.length && /^(-|\*)\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^(-|\*)\s+/, ''))
                index += 1
            }

            blocks.push(
                <ul key={`ul-${blocks.length}`} style={{ margin: 0, paddingLeft: '1.5rem' }}>
                    {items.map((item, itemIndex) => (
                        <li key={`${itemIndex}-${item}`}>{formatInlineMarkdown(item)}</li>
                    ))}
                </ul>,
            )
            continue
        }

        if (/^\d+\.\s+/.test(trimmed)) {
            const items: string[] = []

            while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^\d+\.\s+/, ''))
                index += 1
            }

            blocks.push(
                <ol key={`ol-${blocks.length}`} style={{ margin: 0, paddingLeft: '1.5rem' }}>
                    {items.map((item, itemIndex) => (
                        <li key={`${itemIndex}-${item}`}>{formatInlineMarkdown(item)}</li>
                    ))}
                </ol>,
            )
            continue
        }

        if (trimmed.startsWith('>')) {
            const quoteLines: string[] = []

            while (index < lines.length && lines[index].trim().startsWith('>')) {
                quoteLines.push(lines[index].trim().replace(/^>\s?/, ''))
                index += 1
            }

            blocks.push(
                <blockquote
                    key={`quote-${blocks.length}`}
                    style={{
                        margin: 0,
                        padding: '0.25rem 0 0.25rem 1rem',
                        borderLeft: '4px solid #cbd5e1',
                        color: '#334155',
                    }}
                >
                    {quoteLines.map((quoteLine, quoteIndex) => (
                        <Fragment key={`${quoteIndex}-${quoteLine}`}>
                            {quoteIndex > 0 ? <br /> : null}
                            {formatInlineMarkdown(quoteLine)}
                        </Fragment>
                    ))}
                </blockquote>,
            )
            continue
        }

        if (/^---+$/.test(trimmed)) {
            blocks.push(
                <hr
                    key={`hr-${blocks.length}`}
                    style={{ width: '100%', border: 0, borderTop: '1px solid #cbd5e1' }}
                />,
            )
            index += 1
            continue
        }

        if (
            index + 1 < lines.length &&
            trimmed.includes('|') &&
            isTableSeparatorLine(lines[index + 1])
        ) {
            const headerCells = parseTableRow(trimmed)
            const bodyRows: string[][] = []
            index += 2

            while (index < lines.length) {
                const rowLine = lines[index].trim()
                if (!rowLine || !rowLine.includes('|')) {
                    break
                }

                bodyRows.push(parseTableRow(rowLine))
                index += 1
            }

            blocks.push(
                <div
                    key={`table-${blocks.length}`}
                    style={{
                        overflowX: 'auto',
                        border: '1px solid #cbd5e1',
                        borderRadius: '0.75rem',
                        background: '#fff',
                    }}
                >
                    <table
                        style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            minWidth: '24rem',
                        }}
                    >
                        <thead style={{ background: '#e2e8f0' }}>
                            <tr>
                                {headerCells.map((cell, cellIndex) => (
                                    <th
                                        key={`${cellIndex}-${cell}`}
                                        style={{
                                            textAlign: 'left',
                                            padding: '0.75rem 0.9rem',
                                            borderBottom: '1px solid #cbd5e1',
                                            color: '#0f172a',
                                        }}
                                    >
                                        {formatInlineMarkdown(cell)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {bodyRows.map((row, rowIndex) => (
                                <tr key={`${rowIndex}-${row.join('|')}`}>
                                    {headerCells.map((_, cellIndex) => (
                                        <td
                                            key={`${rowIndex}-${cellIndex}`}
                                            style={{
                                                padding: '0.75rem 0.9rem',
                                                borderTop:
                                                    rowIndex === 0
                                                        ? 'none'
                                                        : '1px solid #e2e8f0',
                                                color: '#1e293b',
                                                verticalAlign: 'top',
                                            }}
                                        >
                                            {formatInlineMarkdown(row[cellIndex] || '')}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>,
            )
            continue
        }

        const paragraphLines: string[] = []
        while (index < lines.length && lines[index].trim()) {
            const candidate = lines[index].trim()
            if (
                candidate.startsWith('```') ||
                /^#{1,6}\s+/.test(candidate) ||
                /^(-|\*)\s+/.test(candidate) ||
                /^\d+\.\s+/.test(candidate) ||
                candidate.startsWith('>') ||
                (index + 1 < lines.length &&
                    candidate.includes('|') &&
                    isTableSeparatorLine(lines[index + 1])) ||
                /^---+$/.test(candidate)
            ) {
                break
            }

            paragraphLines.push(candidate)
            index += 1
        }

        if (paragraphLines.length > 0) {
            blocks.push(
                <p
                    key={`p-${blocks.length}`}
                    style={{ margin: 0, color: '#1e293b', lineHeight: 1.7 }}
                >
                    {formatInlineMarkdown(paragraphLines.join(' '))}
                </p>,
            )
            continue
        }

        index += 1
    }

    return blocks
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

    return [...new Set(candidates.filter((candidate): candidate is string => Boolean(candidate)).map(normalizeBaseUrl))]
}

const discoverApiBase = async (serviceUrl: string | undefined): Promise<string> => {
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

export default function ProjectTab({
    settings,
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
    const [resultMarkdown, setResultMarkdown] = useState<string | null>(null)
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [apiBaseUrl, setApiBaseUrl] = useState<string | null>(null)

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null

    useEffect(() => {
        let isMounted = true

        const loadTemplates = async () => {
            setIsLoadingTemplates(true)
            setErrorMessage(null)

            try {
                const baseUrl = await discoverApiBase(settings.serviceUrl)
                const url = `${baseUrl}/templates`
                const response = await fetch(url)
                const data = await readApiResponse<TemplateOption[]>(response, url)

                if (!response.ok) {
                    throw new Error(`Failed to load the list of templates (${response.status}).`)
                }
                if (!isMounted) {
                    return
                }

                setApiBaseUrl(baseUrl)
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
    }, [settings.serviceUrl])

    useEffect(() => {
        if (!activeRunId) {
            return
        }

        if (!apiBaseUrl) {
            return
        }

        const pollStatus = async () => {
            try {
                const url = `${apiBaseUrl}/pipelines/status/${activeRunId}`
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
                    setResultMarkdown(data.resultMarkdown)
                    setEditableResultMarkdown(data.resultMarkdown || '')
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
    }, [activeRunId, apiBaseUrl])

    const handleRunPipeline = async () => {
        if (!project) {
            setErrorMessage('Project is not available.')
            return
        }

        if (!selectedTemplateUuid) {
            setErrorMessage('Select a DMP template.')
            return
        }

        if (!apiBaseUrl) {
            setErrorMessage('Plugin backend is not available.')
            return
        }

        setIsRunningPipeline(true)
        setErrorMessage(null)
        setSuccessMessage(null)
        setInfoMessage(null)
        setResultMarkdown(null)
        setEditableResultMarkdown('')

        try {
            const { apiUrl, token } = getApiUrlAndToken()
            if (!token) {
                throw new Error('Failed to retrieve the current user\'s authentication token.')
            }

            const url = `${apiBaseUrl}/pipelines/run`
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

            <section
                style={{
                    display: 'grid',
                    gap: '0.75rem',
                    marginTop: '0.5rem',
                    paddingTop: '1rem',
                    borderTop: '1px solid #e2e8f0',
                }}
            >
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1rem',
                        flexWrap: 'wrap',
                    }}
                >
                    <div>
                        <div style={{ fontWeight: 700 }}>Pipeline output</div>
                        <div style={{ color: '#64748b', fontSize: '0.95rem' }}>
                            Preview of the generated document. The render mode is prepared for
                            more output formats later.
                        </div>
                    </div>

                    <div
                        style={{
                            display: 'inline-flex',
                            border: '1px solid #cbd5e1',
                            borderRadius: '999px',
                            overflow: 'hidden',
                            background: '#fff',
                        }}
                    >
                        {(['formatted', 'raw'] as const).map((mode) => (
                            <button
                                key={mode}
                                type="button"
                                onClick={() => setResultRenderMode(mode)}
                                style={{
                                    border: 0,
                                    padding: '0.55rem 0.9rem',
                                    background:
                                        resultRenderMode === mode ? '#0f172a' : 'transparent',
                                    color: resultRenderMode === mode ? '#fff' : '#334155',
                                    cursor: 'pointer',
                                    fontWeight: 600,
                                }}
                            >
                                {mode === 'formatted' ? 'Formatted' : 'Raw'}
                            </button>
                        ))}
                    </div>
                </div>

                <div
                    style={{
                        minHeight: '14rem',
                        padding: '1rem',
                        borderRadius: '1rem',
                        border: '1px solid #cbd5e1',
                        background: '#f8fafc',
                        display: 'grid',
                        gap: '1rem',
                    }}
                >
                    {!resultMarkdown ? (
                        <div style={{ color: '#64748b', lineHeight: 1.6 }}>
                            The generated markdown will appear here after a successful pipeline
                            run.
                        </div>
                    ) : resultRenderMode === 'raw' ? (
                        <textarea
                            value={editableResultMarkdown}
                            onChange={(event) => setEditableResultMarkdown(event.target.value)}
                            style={{
                                margin: 0,
                                color: '#0f172a',
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                                width: '100%',
                                minHeight: '20rem',
                                resize: 'vertical',
                                border: '1px solid #cbd5e1',
                                borderRadius: '0.75rem',
                                padding: '1rem',
                                background: '#fff',
                                lineHeight: 1.6,
                            }}
                        >
                            {editableResultMarkdown}
                        </textarea>
                    ) : (
                        renderMarkdownBlocks(displayedResultMarkdown || '')
                    )}
                </div>
            </section>
        </div>
    )
}
