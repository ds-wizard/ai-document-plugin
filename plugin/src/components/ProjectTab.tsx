import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { useEffect, useState } from 'react'

import { getTemplate, getTemplates, runPipeline, saveEditedPipelineResult } from '@/client'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import { PipelineStatusPoller } from '@/components/PipelineStatusPoller'
import styles from '@/components/ProjectTab.module.css'
import { CUSTOM_TEMPLATE_OPTION, TemplateDropdown } from '@/components/TemplateDropdown'
import { TemplatePreview } from '@/components/TemplatePreview'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import type { ResultRenderMode, TemplateDetail, TemplateOption } from '@/types'

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
    const [resultRunId, setResultRunId] = useState<string | null>(null)
    const [resultMarkdown, setResultMarkdown] = useState<string | null>(null)
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [isSavingEditedVersion, setIsSavingEditedVersion] = useState(false)
    const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<TemplateDetail | null>(
        null,
    )
    const [isLoadingTemplateDetail, setIsLoadingTemplateDetail] = useState(false)

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges = resultMarkdown !== null && editableResultMarkdown !== resultMarkdown
    const isCreatingCustomTemplate = selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION
    const showTemplatePreview =
        Boolean(selectedTemplateUuid) && !isCreatingCustomTemplate && !isLoadingTemplates

    const handleTemplateChange = (templateUuid: string) => {
        setSelectedTemplateUuid(templateUuid)
    }

    const handleTemplateCreated = (savedTemplate: TemplateOption) => {
        setTemplates((currentTemplates) => {
            const filteredTemplates = currentTemplates.filter(
                (template) => template.uuid !== savedTemplate.uuid,
            )
            return [savedTemplate, ...filteredTemplates].sort((left, right) =>
                left.title.localeCompare(right.title),
            )
        })
        setSelectedTemplateUuid(savedTemplate.uuid)
        setErrorMessage(null)
        setSuccessMessage(`Template "${savedTemplate.title}" was saved and added to the dropdown.`)
    }

    useEffect(() => {
        let isMounted = true

        const loadTemplates = async () => {
            setIsLoadingTemplates(true)
            setErrorMessage(null)

            try {
                const templates = await getTemplates()
                if (!isMounted) {
                    return
                }

                setTemplates(templates)
                setSelectedTemplateUuid((currentValue) => currentValue || '')
            } catch (error) {
                if (!isMounted) {
                    console.error(error)
                    return
                }

                // Use error.name === 'TypeError' as a more robust check for "failed to fetch"
                let message: string
                if (error instanceof TypeError) {
                    message = 'Cannot connect to the server.'
                } else if (error instanceof Error) {
                    message = error.message
                } else {
                    message = 'Unable to load the list of templates.'
                }
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
        if (!showTemplatePreview) {
            setSelectedTemplateDetail(null)
            setIsLoadingTemplateDetail(false)
            return
        }

        if (selectedTemplateDetail?.uuid === selectedTemplateUuid) {
            return
        }

        let isMounted = true

        const loadTemplateDetail = async () => {
            setIsLoadingTemplateDetail(true)

            try {
                const detail = await getTemplate(selectedTemplateUuid)
                if (isMounted) {
                    setSelectedTemplateDetail(detail)
                }
            } catch {
                if (isMounted) {
                    setSelectedTemplateDetail(null)
                }
            } finally {
                if (isMounted) {
                    setIsLoadingTemplateDetail(false)
                }
            }
        }

        void loadTemplateDetail()

        return () => {
            isMounted = false
        }
    }, [selectedTemplateDetail?.uuid, selectedTemplateUuid, showTemplatePreview])

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

        setIsRunningPipeline(true)
        setErrorMessage(null)
        setSuccessMessage(null)
        setInfoMessage(null)
        setResultRunId(null)
        setResultMarkdown(null)
        setEditableResultMarkdown('')

        try {
            const data = await runPipeline({
                questionnaireUuid: project.uuid,
                templateUuid: selectedTemplateUuid,
                llmModel: settings.model || null,
                llmApiKey: settings.apiKey || null,
                llmApiUrl: settings.apiUrl || null,
                llmMaxWorkers: settings.maxWorkers ?? null,
            })

            setActiveRunId(data.runId)
            setInfoMessage(`Pipeline has been accepted for the template "${data.templateTitle}".`)
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Pipeline execution failed.'
            setErrorMessage(message)
            setIsRunningPipeline(false)
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

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(resultRunId, editableResultMarkdown)

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

                {activeRunId ? (
                    <PipelineStatusPoller
                        activeRunId={activeRunId}
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
                    <TemplateDropdown
                        value={selectedTemplateUuid}
                        onChange={handleTemplateChange}
                        templates={templates}
                        isLoading={isLoadingTemplates}
                        disabled={isRunningPipeline || !project}
                    />
                </label>

                {selectedTemplateDetail ? (
                    <TemplatePreview
                        content={
                            selectedTemplateDetail?.uuid === selectedTemplateUuid
                                ? selectedTemplateDetail.content
                                : undefined
                        }
                        isLoading={
                            isLoadingTemplateDetail ||
                            selectedTemplateDetail?.uuid !== selectedTemplateUuid
                        }
                    />
                ) : null}
                {isCreatingCustomTemplate ? (
                    <CustomTemplateSection onTemplateCreated={handleTemplateCreated} />
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
