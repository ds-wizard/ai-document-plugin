import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'

import { createTemplate, getTemplate, getTemplates } from '@/client'
import { Alert } from '@/components/Alert'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import styles from '@/components/DmpTemplateSection.module.css'
import { TemplateTitlePreview } from '@/components/TemplateTitlePreview'
import type { ApiTemplateContent, TemplateDetail, TemplateOption } from '@/types'

const CUSTOM_TEMPLATE_OPTION = '__custom_template__'

type DmpTemplateSectionProps = {
    projectAvailable: boolean
    hasLastExport: boolean
    onRunPipeline: (templateUuid: string) => void
    onShowLastExport: () => void
}

export function DmpTemplateSection({
    projectAvailable,
    hasLastExport,
    onRunPipeline,
    onShowLastExport,
}: DmpTemplateSectionProps) {
    const [templates, setTemplates] = useState<TemplateOption[]>([])
    const [selectedTemplateUuid, setSelectedTemplateUuid] = useState('')
    const [localTemplateTitle, setLocalTemplateTitle] = useState('')
    const [localTemplateJson, setLocalTemplateJson] = useState('')
    const [localTemplateFileName, setLocalTemplateFileName] = useState('')
    const [localTemplateError, setLocalTemplateError] = useState<string | null>(null)
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(true)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [isCreatingTemplate, setIsCreatingTemplate] = useState(false)
    const [isTemplateDropdownOpen, setIsTemplateDropdownOpen] = useState(false)
    const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<TemplateDetail | null>(
        null,
    )
    const [isLoadingTemplateDetail, setIsLoadingTemplateDetail] = useState(false)
    const templateDropdownRef = useRef<HTMLDivElement | null>(null)

    const isCreatingCustomTemplate = selectedTemplateUuid === CUSTOM_TEMPLATE_OPTION
    const showTemplatePreview =
        Boolean(selectedTemplateUuid) && !isCreatingCustomTemplate && !isLoadingTemplates
    const selectedTemplateLabel = useMemo(() => {
        if (!selectedTemplateUuid) {
            if (isLoadingTemplates) {
                return 'Loading templates...'
            }

            return 'Select a template'
        }

        if (isCreatingCustomTemplate) {
            return 'Custom template...'
        }

        const selectedTemplate = templates.find(
            (template) => template.uuid === selectedTemplateUuid,
        )
        if (!selectedTemplate) {
            return 'Select a template'
        }

        return `${selectedTemplate.title}`
    }, [isCreatingCustomTemplate, isLoadingTemplates, selectedTemplateUuid, templates])

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

    useEffect(() => {
        if (!showTemplatePreview) {
            setSelectedTemplateDetail(null)
            setIsLoadingTemplateDetail(false)
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
    }, [selectedTemplateUuid, showTemplatePreview])

    const handleRunPipeline = () => {
        if (!selectedTemplateUuid) {
            setErrorMessage('Select a DMP template.')
            return
        }

        if (isCreatingCustomTemplate) {
            setErrorMessage('Create a custom template or select an existing one first.')
            return
        }

        setErrorMessage(null)
        setSuccessMessage(null)
        onRunPipeline(selectedTemplateUuid)
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
            const content = JSON.parse(trimmedJson) as ApiTemplateContent

            setIsCreatingTemplate(true)
            const data = await createTemplate({
                title: trimmedTitle,
                content,
            })

            const savedTemplate: TemplateOption = {
                uuid: data.uuid,
                title: data.title,
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

    return (
        <>
            <label className={styles.label}>
                <div className={styles.dropdown} ref={templateDropdownRef}>
                    <button
                        type="button"
                        disabled={isLoadingTemplates || !projectAvailable}
                        className={styles.dropdownToggle}
                        onClick={() => setIsTemplateDropdownOpen((currentValue) => !currentValue)}
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

            {showTemplatePreview ? (
                <TemplateTitlePreview
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

            <div className={styles.actionRow}>
                <button
                    type="button"
                    onClick={() => handleRunPipeline()}
                    disabled={
                        isLoadingTemplates ||
                        !selectedTemplateUuid ||
                        !projectAvailable ||
                        isCreatingCustomTemplate
                    }
                    className={`btn btn-primary btn-wide ${styles.runButton}`}
                >
                    Run pipeline
                </button>

                {hasLastExport ? (
                    <button
                        type="button"
                        onClick={onShowLastExport}
                        className={`btn btn-outline-secondary btn-wide ${styles.lastExportButton}`}
                    >
                        Show last export
                    </button>
                ) : null}
            </div>

            <Alert variant="error">{errorMessage}</Alert>
            <Alert variant="success">{successMessage}</Alert>
        </>
    )
}
