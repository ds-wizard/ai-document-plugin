import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react'

import { createTemplate, updateTemplate } from '@/client'
import styles from '@/components/CustomTemplateSection.module.css'
import { TemplateStructureEditor } from '@/components/TemplateStructureEditor'
import type { ApiTemplateContent, TemplateOption, TemplateScope } from '@/types'

export type EditingTemplate = {
    uuid: string
    title: string
    content: ApiTemplateContent
}

type CustomTemplateSectionProps = {
    scope: TemplateScope
    onSaved: (template: TemplateOption) => void
    editingTemplate?: EditingTemplate | null
    onCancel?: () => void
}

const scopeNoun = (scope: TemplateScope): string =>
    scope === 'tenant' ? 'tenant-wide template' : 'personal template'

export function CustomTemplateSection({
    scope,
    onSaved,
    editingTemplate = null,
    onCancel,
}: CustomTemplateSectionProps) {
    const isEditing = editingTemplate !== null
    const [title, setTitle] = useState(editingTemplate?.title ?? '')
    const [json, setJson] = useState(
        editingTemplate ? JSON.stringify(editingTemplate.content, null, 2) : '',
    )
    const [fileName, setFileName] = useState('')
    const [error, setError] = useState<string | null>(null)
    const [isSaving, setIsSaving] = useState(false)
    const [inputMode, setInputMode] = useState<'visual' | 'file'>('visual')
    const [isDraggingFile, setIsDraggingFile] = useState(false)
    const previousFileNameRef = useRef(fileName)
    const dragDepthRef = useRef(0)

    // Reset the form whenever we switch which template is being edited (or created).
    useEffect(() => {
        setTitle(editingTemplate?.title ?? '')
        setJson(editingTemplate ? JSON.stringify(editingTemplate.content, null, 2) : '')
        setFileName('')
        setError(null)
        setInputMode('visual')
    }, [editingTemplate])

    const processTemplateFile = async (file: File) => {
        try {
            const content = await file.text()
            setFileName(file.name)
            setJson(content)
            if (!title.trim()) {
                setTitle(file.name.replace(/\.json$/i, ''))
            }
            setError(null)
        } catch {
            setError('Failed to read the selected JSON file.')
        }
    }

    const handleFileInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) {
            setFileName('')
            return
        }

        await processTemplateFile(file)
        event.target.value = ''
    }

    const submitTemplateFile = (file: File) => {
        void processTemplateFile(file)
    }

    const handleDragEnter = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault()
        dragDepthRef.current += 1
        setIsDraggingFile(true)
    }

    const handleDragLeave = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault()
        dragDepthRef.current -= 1
        if (dragDepthRef.current <= 0) {
            dragDepthRef.current = 0
            setIsDraggingFile(false)
        }
    }

    const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault()
    }

    const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault()
        dragDepthRef.current = 0
        setIsDraggingFile(false)

        const file = event.dataTransfer.files?.[0]
        if (file) {
            submitTemplateFile(file)
        }
    }

    const handleSave = async () => {
        const trimmedTitle = title.trim()
        const trimmedJson = json.trim()

        if (!trimmedTitle) {
            setError('Enter a template title.')
            return
        }

        if (!trimmedJson) {
            setError('Insert or upload template JSON.')
            return
        }

        try {
            const parsed = JSON.parse(trimmedJson) as { sections?: unknown }
            if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sections)) {
                throw new Error('Template JSON must contain a top-level "sections" array.')
            }

            setIsSaving(true)
            const data = isEditing
                ? await updateTemplate({
                      uuid: editingTemplate.uuid,
                      title: trimmedTitle,
                      content: parsed,
                  })
                : await createTemplate({
                      title: trimmedTitle,
                      content: parsed,
                      scope,
                  })

            if (!isEditing) {
                setTitle('')
                setJson('')
                setFileName('')
            }
            setError(null)
            onSaved(data)
        } catch (saveError) {
            setError(saveError instanceof Error ? saveError.message : 'Template JSON is not valid.')
        } finally {
            setIsSaving(false)
        }
    }

    useEffect(() => {
        const fileNameChanged = fileName !== previousFileNameRef.current
        previousFileNameRef.current = fileName

        if (inputMode === 'file' && fileName && fileNameChanged) {
            setInputMode('visual')
        }
    }, [fileName, inputMode])

    const heading = isEditing
        ? `Edit ${scopeNoun(scope)}`
        : `Create ${scopeNoun(scope)}`

    const saveLabel = isEditing ? 'Update template' : 'Save template'
    const savingLabel = isEditing ? 'Updating template...' : 'Saving template...'

    return (
        <section className={styles.root}>
            <div>
                <h5 className={styles.title}>{heading}</h5>
            </div>

            <label className={styles.label}>
                <span className={styles.labelText}>Template title</span>
                <input
                    type="text"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="My custom DMP template"
                    className="form-control"
                />
            </label>

            <div className={styles.label}>
                <span className={styles.labelText}>Template structure</span>
                <div className={`${styles.segmentedControl} btn-group`} role="group">
                    {(
                        [
                            { mode: 'visual' as const, label: 'Visual editor' },
                            { mode: 'file' as const, label: 'From file' },
                        ] as const
                    ).map(({ mode, label }) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => setInputMode(mode)}
                            className={
                                inputMode === mode
                                    ? 'btn btn-secondary'
                                    : 'btn btn-outline-secondary'
                            }
                        >
                            {label}
                        </button>
                    ))}
                </div>

                {inputMode === 'visual' ? (
                    <TemplateStructureEditor value={json} onChange={setJson} />
                ) : (
                    <label
                        className={`${styles.fileDropZone} ${
                            isDraggingFile ? styles.fileDropZoneDragging : ''
                        } ${fileName ? styles.fileDropZoneFilled : ''}`}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                    >
                        <input
                            type="file"
                            accept=".json,application/json"
                            onChange={(event) => void handleFileInputChange(event)}
                            className={styles.hiddenInput}
                        />
                        <span className={styles.fileDropIcon} aria-hidden="true">
                            <i className="fas fa-upload" />
                        </span>
                        <span className={styles.fileDropTitle}>
                            {fileName || 'Drop JSON template here'}
                        </span>
                        <span className={styles.fileDropHint}>
                            {fileName
                                ? 'Click or drop another file to replace'
                                : 'or click anywhere to browse'}
                        </span>
                    </label>
                )}
            </div>

            <div className={styles.actions}>
                <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={isSaving}
                    className={`${styles.saveButton} btn btn-primary btn-wide`}
                >
                    {isSaving ? savingLabel : saveLabel}
                </button>

                {onCancel ? (
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={isSaving}
                        className="btn btn-outline-secondary"
                    >
                        Cancel
                    </button>
                ) : null}
            </div>

            {error ? <div className={styles.alert}>{error}</div> : null}
        </section>
    )
}
