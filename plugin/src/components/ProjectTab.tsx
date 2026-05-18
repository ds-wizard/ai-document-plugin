import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { ChangeEvent, useEffect, useState } from 'react'

import { createTemplate, getTemplates, runPipeline, saveEditedPipelineResult } from '@/client'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import { PipelineStatusPoller } from '@/components/PipelineStatusPoller'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import type { ResultRenderMode, TemplateOption } from '@/types'

const CUSTOM_TEMPLATE_OPTION = '__custom_template__'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const [templates, setTemplates] = useState<TemplateOption[]>([])
    const [selectedTemplateUuid, setSelectedTemplateUuid] = useState('')
    const [localTemplateTitle, setLocalTemplateTitle] = useState('')
    const [localTemplateJson, setLocalTemplateJson] = useState('')
    const [localTemplateFileName, setLocalTemplateFileName] = useState('')
    const [localTemplateError, setLocalTemplateError] = useState<string | null>(null)
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(true)
    const [isRunningPipeline, setIsRunningPipeline] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [infoMessage, setInfoMessage] = useState<string | null>(null)
    const [activeRunId, setActiveRunId] = useState<string | null>(null)
    const [resultRunId, setResultRunId] = useState<string | null>(null)
    const [resultMarkdown, setResultMarkdown] = useState<string | null>(null)
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [apiBaseUrl, setApiBaseUrl] = useState<string | null>(null)
    const [isSavingEditedVersion, setIsSavingEditedVersion] = useState(false)
    const [isCreatingTemplate, setIsCreatingTemplate] = useState(false)

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges = resultMarkdown !== null && editableResultMarkdown !== resultMarkdown
    const isCreatingCustomTemplate = selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION

    useEffect(() => {
        let isMounted = true

        const loadTemplates = async () => {
            setIsLoadingTemplates(true)
            setErrorMessage(null)

            try {
                const { baseUrl, templates } = await getTemplates(settings.serviceUrl)
                if (!isMounted) {
                    return
                }

                setApiBaseUrl(baseUrl)
                setTemplates(
                    templates.map((template) => ({ ...template, source: 'database' as const })),
                )
                setSelectedTemplateUuid((currentValue) => currentValue || '')
            } catch (error) {
                if (!isMounted) {
                    console.error(error)
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

    const handleRunPipeline = async () => {
        if (!project) {
            setErrorMessage('Project is not available.')
            return
        }

        if (!selectedTemplateUuid) {
            setErrorMessage('Select a DMP template.')
            return
        }

        if (isCreatingCustomTemplate) {
            setErrorMessage('Create a custom template or select an existing one first.')
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
        setResultRunId(null)
        setResultMarkdown(null)
        setEditableResultMarkdown('')

        try {
            const { apiUrl, token } = getApiUrlAndToken()
            if (!token) {
                throw new Error("Failed to retrieve the current user's authentication token.")
            }

            const data = await runPipeline({
                apiBaseUrl,
                questionnaireUuid: project.uuid,
                templateUuid: selectedTemplateUuid,
                token,
                apiUrl,
                llmModel: settings.model || null,
                llmApiKey: settings.apiKey || null,
                llmApiUrl: settings.apiUrl || null,
            })

            setActiveRunId(data.runId)
            setInfoMessage(`Pipeline has been accepted for the template "${data.templateTitle}".`)
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Pipeline execution failed.'
            setErrorMessage(message)
            setIsRunningPipeline(false)
        }
    }

    const handleLocalTemplateFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) {
            setLocalTemplateFileName('')
            return
        }

        try {
            const content = await file.text()
            setLocalTemplateFileName(file.name)
            setLocalTemplateJson(content)
            if (!localTemplateTitle.trim()) {
                setLocalTemplateTitle(file.name.replace(/\.json$/i, ''))
            }
            setLocalTemplateError(null)
        } catch {
            setLocalTemplateError('Failed to read the selected JSON file.')
        } finally {
            event.target.value = ''
        }
    }

    const handleAddLocalTemplate = async () => {
        const trimmedTitle = localTemplateTitle.trim()
        const trimmedJson = localTemplateJson.trim()

        if (!trimmedTitle) {
            setLocalTemplateError('Enter a template title.')
            return
        }

        if (!trimmedJson) {
            setLocalTemplateError('Insert or upload template JSON.')
            return
        }

        try {
            const parsed = JSON.parse(trimmedJson) as { sections?: unknown }
            if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sections)) {
                throw new Error('Template JSON must contain a top-level "sections" array.')
            }

            if (!apiBaseUrl) {
                throw new Error('Plugin backend is not available.')
            }

            setIsCreatingTemplate(true)
            const data = await createTemplate({
                apiBaseUrl,
                title: trimmedTitle,
                content: parsed,
            })

            const savedTemplate: TemplateOption = {
                uuid: data.uuid,
                title: data.title,
                source: 'database',
            }

            setTemplates((currentTemplates) => {
                const filteredTemplates = currentTemplates.filter(
                    (template) => template.uuid !== savedTemplate.uuid,
                )
                return [savedTemplate, ...filteredTemplates].sort((left, right) =>
                    left.title.localeCompare(right.title),
                )
            })
            setSelectedTemplateUuid(savedTemplate.uuid)
            setLocalTemplateTitle('')
            setLocalTemplateJson('')
            setLocalTemplateFileName('')
            setLocalTemplateError(null)
            setErrorMessage(null)
            setSuccessMessage(`Template "${trimmedTitle}" was saved and added to the dropdown.`)
        } catch (error) {
            setLocalTemplateError(
                error instanceof Error ? error.message : 'Template JSON is not valid.',
            )
        } finally {
            setIsCreatingTemplate(false)
        }
    }

    const handleCopyMarkdown = async () => {
        if (!displayedResultMarkdown) {
            return
        }

        try {
            await navigator.clipboard.writeText(displayedResultMarkdown)
            setErrorMessage(null)
            setSuccessMessage('Markdown has been copied to the clipboard.')
        } catch {
            setErrorMessage('Failed to copy markdown to the clipboard.')
        }
    }

    const handleDownloadMarkdown = () => {
        if (!displayedResultMarkdown) {
            return
        }

        const blob = new Blob([displayedResultMarkdown], { type: 'text/markdown;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${selectedTemplateUuid || 'pipeline-output'}.md`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        setErrorMessage(null)
        setSuccessMessage('Markdown download has started.')
    }

    const handleSaveEditedVersion = async () => {
        if (!resultRunId || !resultMarkdown) {
            setErrorMessage('There is no pipeline result to save yet.')
            return
        }

        if (!apiBaseUrl) {
            setErrorMessage('Plugin backend is not available.')
            return
        }

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(
                apiBaseUrl,
                resultRunId,
                editableResultMarkdown,
            )

            setResultMarkdown(data.resultMarkdown)
            setEditableResultMarkdown(data.resultMarkdown || '')
            setErrorMessage(null)
            setSuccessMessage('Edited markdown has been saved.')
        } catch (error) {
            setErrorMessage(
                error instanceof Error ? error.message : 'Failed to save the edited version.',
            )
        } finally {
            setIsSavingEditedVersion(false)
        }
    }

    return (
        <div className="ai-doc-root">
            <div>
                <h1 className="ai-doc-page-title">AI Document Generation</h1>
                <p className="ai-doc-page-lead">
                    Select a DMP template from the database and run the pipeline on the current
                    project.
                </p>
            </div>

            {!project ? (
                <div className="ai-doc-alert ai-doc-alert-warning">
                    The project is not loaded; the pipeline cannot be started yet.
                </div>
            ) : null}

            {activeRunId && apiBaseUrl ? (
                <PipelineStatusPoller
                    activeRunId={activeRunId}
                    apiBaseUrl={apiBaseUrl}
                    setActiveRunId={setActiveRunId}
                    setEditableResultMarkdown={setEditableResultMarkdown}
                    setErrorMessage={setErrorMessage}
                    setInfoMessage={setInfoMessage}
                    setIsRunningPipeline={setIsRunningPipeline}
                    setResultMarkdown={setResultMarkdown}
                    setResultRunId={setResultRunId}
                    setSuccessMessage={setSuccessMessage}
                />
            ) : null}

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">DMP template</span>
                <select
                    value={selectedTemplateUuid}
                    onChange={(event) => {
                        setSelectedTemplateUuid(event.target.value)
                        setLocalTemplateError(null)
                    }}
                    disabled={isLoadingTemplates || isRunningPipeline || !project}
                    className="ai-doc-input"
                >
                    <option value="">
                        {isLoadingTemplates
                            ? 'Loading templates...'
                            : templates.length === 0
                              ? 'Select a template option'
                              : 'Select a template'}
                    </option>
                    {templates.map((template) => (
                        <option key={template.uuid} value={template.uuid}>
                            {template.title}
                            {template.source === 'local' ? ' (local)' : ''}
                        </option>
                    ))}
                    <option value={CUSTOM_TEMPLATE_OPTION}>Custom template...</option>
                </select>
            </label>

            {isCreatingCustomTemplate ? (
                <CustomTemplateSection
                    localTemplateTitle={localTemplateTitle}
                    localTemplateJson={localTemplateJson}
                    localTemplateFileName={localTemplateFileName}
                    localTemplateError={localTemplateError}
                    isCreatingTemplate={isCreatingTemplate}
                    onLocalTemplateTitleChange={setLocalTemplateTitle}
                    onLocalTemplateJsonChange={setLocalTemplateJson}
                    onLocalTemplateFileUpload={handleLocalTemplateFileUpload}
                    onAddLocalTemplate={() => void handleAddLocalTemplate()}
                />
            ) : null}

            <button
                type="button"
                onClick={() => void handleRunPipeline()}
                disabled={
                    isLoadingTemplates || isRunningPipeline || !selectedTemplateUuid || !project
                }
                className="ai-doc-button ai-doc-button-primary"
            >
                {isRunningPipeline ? 'Running pipeline...' : 'Run pipeline'}
            </button>

            {project ? (
                <div className="ai-doc-project-name">
                    Project: <strong>{project.name}</strong>
                </div>
            ) : null}

            {errorMessage ? (
                <div className="ai-doc-alert ai-doc-alert-error">{errorMessage}</div>
            ) : null}

            {infoMessage ? <div className="ai-doc-alert ai-doc-alert-info">{infoMessage}</div> : null}

            {successMessage ? (
                <div className="ai-doc-alert ai-doc-alert-success">{successMessage}</div>
            ) : null}

            <PipelineResultPanel
                resultMarkdown={resultMarkdown}
                editableResultMarkdown={editableResultMarkdown}
                resultRenderMode={resultRenderMode}
                isSavingEditedVersion={isSavingEditedVersion}
                hasResultChanges={hasResultChanges}
                displayedResultMarkdown={displayedResultMarkdown}
                onResultRenderModeChange={setResultRenderMode}
                onEditableResultMarkdownChange={setEditableResultMarkdown}
                onCopyMarkdown={() => void handleCopyMarkdown()}
                onDownloadMarkdown={handleDownloadMarkdown}
                onSaveEditedVersion={() => void handleSaveEditedVersion()}
            />
        </div>
    )
}
