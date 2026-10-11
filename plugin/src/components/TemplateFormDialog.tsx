import { ChangeEvent, DragEvent, useRef, useState } from 'react'
import { toast } from 'sonner'

import { createTemplate, updateTemplate } from '@/client'
import { CoverPagePreview } from '@/components/CoverPagePreview'
import { Modal } from '@/components/Modal'
import styles from '@/components/TemplateFormDialog.module.css'
import { TemplateStructureEditor } from '@/components/TemplateStructureEditor'
import type { ApiTemplateContent, TemplateDetail, TemplateOption, TemplateScope } from '@/types'

/** What the form works on: an existing template to edit, or `'new'` to create one. */
export type TemplateFormTarget = TemplateDetail | 'new'

type TemplateFormDialogProps = {
    scope: TemplateScope
    target: TemplateFormTarget
    onSaved: (template: TemplateOption) => void
    onClose: () => void
}

type InputMode = 'visual' | 'file'

const INPUT_MODES: { mode: InputMode; label: string }[] = [
    { mode: 'visual', label: 'Visual editor' },
    { mode: 'file', label: 'From file' },
]

const scopeNoun = (scope: TemplateScope): string =>
    scope === 'tenant' ? 'tenant-wide template' : 'personal template'

const parseTemplateContent = (json: string): ApiTemplateContent => {
    const parsed = JSON.parse(json) as { sections?: unknown } | null
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sections)) {
        throw new Error('Template JSON must contain a top-level "sections" array.')
    }
    return parsed as ApiTemplateContent
}

/**
 * Dialog with the form for creating or editing a template.
 *
 * Mount it to open it: the form starts from `target` each time, so nothing has to be reset.
 */
export function TemplateFormDialog({ scope, target, onSaved, onClose }: TemplateFormDialogProps) {
    const editedTemplate = target === 'new' ? null : target
    const [hasCoverPage, setHasCoverPage] = useState(editedTemplate?.hasCoverPage ?? false)
    const [title, setTitle] = useState(editedTemplate?.title ?? '')
    const [json, setJson] = useState(
        editedTemplate ? JSON.stringify(editedTemplate.content, null, 2) : '',
    )
    const [fileName, setFileName] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const [inputMode, setInputMode] = useState<InputMode>('visual')
    const [isDraggingFile, setIsDraggingFile] = useState(false)
    const dragDepthRef = useRef(0)

    const processTemplateFile = async (file: File) => {
        try {
            const content = await file.text()
            setFileName(file.name)
            setJson(content)
            if (!title.trim()) {
                setTitle(file.name.replace(/\.json$/i, ''))
            }
            setInputMode('visual')
        } catch {
            toast.error('Failed to read the selected JSON file.')
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
            void processTemplateFile(file)
        }
    }

    const handleSave = async () => {
        const trimmedTitle = title.trim()
        const trimmedJson = json.trim()

        if (!trimmedTitle) {
            toast.error('Enter a template title.')
            return
        }

        if (!trimmedJson) {
            toast.error('Insert or upload template JSON.')
            return
        }

        try {
            const template = {
                title: trimmedTitle,
                content: parseTemplateContent(trimmedJson),
                hasCoverPage,
            }

            setIsSaving(true)
            const saved = editedTemplate
                ? await updateTemplate({ ...template, uuid: editedTemplate.uuid })
                : await createTemplate({ ...template, scope })

            onSaved(saved)
        } catch (saveError) {
            toast.error(
                saveError instanceof Error ? saveError.message : 'Template JSON is not valid.',
            )
        } finally {
            setIsSaving(false)
        }
    }

    const noun = scopeNoun(scope)
    const saveLabel = editedTemplate ? 'Update template' : 'Save template'
    const savingLabel = editedTemplate ? 'Updating template...' : 'Saving template...'

    return (
        <Modal
            open
            title={editedTemplate ? `Edit ${noun}` : `Create ${noun}`}
            onClose={onClose}
            closeDisabled={isSaving}
            footer={
                <>
                    <button
                        type="button"
                        onClick={() => void handleSave()}
                        disabled={isSaving}
                        className="btn btn-primary btn-wide"
                    >
                        {isSaving ? savingLabel : saveLabel}
                    </button>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isSaving}
                        className="btn btn-outline-secondary"
                    >
                        Cancel
                    </button>
                </>
            }
        >
            <label className="ai-doc-field">
                <span className="ai-doc-field-label">Template title</span>
                <input
                    type="text"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="My custom DMP template"
                    className="form-control"
                />
            </label>

            <div className={styles.metadataSection}>
                <label className={styles.metadataOption}>
                    <input
                        type="checkbox"
                        checked={hasCoverPage}
                        onChange={(event) => setHasCoverPage(event.target.checked)}
                        disabled={isSaving}
                    />
                    <span>Include a cover page with DMP metadata and project information</span>
                </label>
                <CoverPagePreview />
            </div>

            <div className="ai-doc-field">
                <span className="ai-doc-field-label">Template structure</span>
                <div className="ai-doc-segmented-control btn-group" role="group">
                    {INPUT_MODES.map(({ mode, label }) => (
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
        </Modal>
    )
}
