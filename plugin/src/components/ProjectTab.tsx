import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'

import { createTemplate, getTemplates, runPipeline, saveEditedPipelineResult } from '@/client'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import { PipelineStatusPoller } from '@/components/PipelineStatusPoller'
import styles from '@/components/ProjectTab.module.css'
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
    const [isTemplateDropdownOpen, setIsTemplateDropdownOpen] = useState(false)
    const templateDropdownRef = useRef<HTMLDivElement | null>(null)

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges = resultMarkdown !== null && editableResultMarkdown !== resultMarkdown
    const isCreatingCustomTemplate = selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION
    const selectedTemplateLabel = useMemo(() => {
        if (!selectedTemplateUuid) {
            if (isLoadingTemplates) {
                return 'Loading templates...'
            }

            return templates.length === 0 ? 'Select a template option' : 'Select a template'
        }

        if (selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION) {
            return 'Custom template...'
        }

        const selectedTemplate = templates.find(
            (template) => template.uuid === selectedTemplateUuid,
        )
        if (!selectedTemplate) {
            return 'Select a template'
        }

        return `${selectedTemplate.title}${selectedTemplate.source === 'local' ? ' (local)' : ''}`
    }, [isLoadingTemplates, selectedTemplateUuid, templates])

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

    useEffect(() => {
        if (!isTemplateDropdownOpen) {
            return
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (!templateDropdownRef.current?.contains(event.target as Node)) {
                setIsTemplateDropdownOpen(false)
            }
        }

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsTemplateDropdownOpen(false)
            }
        }

        document.addEventListener('mousedown', handlePointerDown)
        document.addEventListener('keydown', handleEscape)

        return () => {
            document.removeEventListener('mousedown', handlePointerDown)
            document.removeEventListener('keydown', handleEscape)
        }
    }, [isTemplateDropdownOpen])

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
        <div className="Projects__Detail__Content Projects__Detail__Content--Metrics">
            <div className={`questionnaire__summary-report container ${styles.root}`}>
                <div>
                    <h2 className={styles.title}>AI Document Generation</h2>
                    <p className={styles.lead}>
                        Select a DMP template from the database and run the pipeline on the current
                        project.
                    </p>
                </div>

                {!project ? (
                    <div className={`${styles.alert} ${styles.warningAlert}`}>
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

                <label className={styles.label}>
                    <h4>DMP template</h4>
                    <div className={styles.dropdown} ref={templateDropdownRef}>
                        <button
                            type="button"
                            disabled={isLoadingTemplates || isRunningPipeline || !project}
                            className={styles.dropdownToggle}
                            onClick={() =>
                                setIsTemplateDropdownOpen((currentValue) => !currentValue)
                            }
                            aria-expanded={isTemplateDropdownOpen}
                        >
                            <span>{selectedTemplateLabel}</span>
                            <span className={styles.dropdownCaret} aria-hidden="true">
                                ▼
                            </span>
                        </button>

                        {isTemplateDropdownOpen ? (
                            <div className={styles.dropdownMenu}>
                                {templates.map((template) => (
                                    <button
                                        key={template.uuid}
                                        type="button"
                                        className={`${styles.dropdownItem} ${
                                            selectedTemplateUuid === template.uuid
                                                ? styles.dropdownItemActive
                                                : ''
                                        }`}
                                        onClick={() => {
                                            setSelectedTemplateUuid(template.uuid)
                                            setLocalTemplateError(null)
                                            setIsTemplateDropdownOpen(false)
                                        }}
                                    >
                                        {template.title}
                                        {template.source === 'local' ? ' (local)' : ''}
                                    </button>
                                ))}

                                <button
                                    type="button"
                                    className={`${styles.dropdownItem} ${
                                        selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION
                                            ? styles.dropdownItemActive
                                            : ''
                                    }`}
                                    onClick={() => {
                                        setSelectedTemplateUuid(CUSTOM_TEMPLATE_OPTION)
                                        setLocalTemplateError(null)
                                        setIsTemplateDropdownOpen(false)
                                    }}
                                >
                                    Custom template...
                                </button>
                            </div>
                        ) : null}
                    </div>
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
                        isLoadingTemplates ||
                        isRunningPipeline ||
                        !selectedTemplateUuid ||
                        !project ||
                        isCreatingCustomTemplate
                    }
                    className={`btn btn-primary btn-wide ${styles.runButton}`}
                >
                    {isRunningPipeline ? 'Running pipeline...' : 'Run pipeline'}
                </button>

                {project ? (
                    <div className={styles.projectName}>
                        Project: <strong>{project.name}</strong>
                    </div>
                ) : null}

                {errorMessage ? (
                    <div className={`${styles.alert} ${styles.errorAlert}`}>{errorMessage}</div>
                ) : null}

                {infoMessage ? (
                    <div className={`${styles.alert} ${styles.infoAlert}`}>{infoMessage}</div>
                ) : null}

                {successMessage ? (
                    <div className={`${styles.alert} ${styles.successAlert}`}>{successMessage}</div>
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
        </div>
    )
}
