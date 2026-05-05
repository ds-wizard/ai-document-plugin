import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { useEffect, useState } from 'react'

import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'

type TemplateOption = {
    uuid: string
    title: string
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

    useEffect(() => {
        let isMounted = true

        const loadTemplates = async () => {
            setIsLoadingTemplates(true)
            setErrorMessage(null)

            try {
                const response = await fetch(`${__API_URL__}/templates`)
                if (!response.ok) {
                    throw new Error(`Nepodarilo se nacist seznam sablon (${response.status}).`)
                }

                const data: TemplateOption[] = await response.json()
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

    const handleRunPipeline = async () => {
        if (!project) {
            setErrorMessage('Projekt neni k dispozici.')
            return
        }

        if (!selectedTemplateUuid) {
            setErrorMessage('Vyberte DMP template.')
            return
        }

        setIsRunningPipeline(true)
        setErrorMessage(null)
        setSuccessMessage(null)

        try {
            const response = await fetch(`${__API_URL__}/pipelines/run`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    questionnaireUuid: project.uuid,
                    templateUuid: selectedTemplateUuid,
                }),
            })

            const data = (await response.json()) as { detail?: string; templateTitle?: string }

            if (!response.ok) {
                throw new Error(data.detail || 'Spusteni pipeline selhalo.')
            }

            setSuccessMessage(`Pipeline byla spustena pro template "${data.templateTitle ?? 'bez nazvu'}".`)
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Spusteni pipeline selhalo.'
            setErrorMessage(message)
        } finally {
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
