import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react'

import { Alert } from '@/components/Alert'
import styles from '@/components/CustomTemplateSection.module.css'
import { TemplateStructureEditor } from '@/components/TemplateStructureEditor'

type CustomTemplateSectionProps = {
    localTemplateTitle: string
    localTemplateJson: string
    localTemplateFileName: string
    localTemplateError: string | null
    isCreatingTemplate: boolean
    onLocalTemplateTitleChange: (value: string) => void
    onLocalTemplateJsonChange: (value: string) => void
    onLocalTemplateFileUpload: (event: ChangeEvent<HTMLInputElement>) => void
    onAddLocalTemplate: () => void
}

export function CustomTemplateSection({
    localTemplateTitle,
    localTemplateJson,
    localTemplateFileName,
    localTemplateError,
    isCreatingTemplate,
    onLocalTemplateTitleChange,
    onLocalTemplateJsonChange,
    onLocalTemplateFileUpload,
    onAddLocalTemplate,
}: CustomTemplateSectionProps) {
    const [inputMode, setInputMode] = useState<'visual' | 'file'>('visual')
    const [isDraggingFile, setIsDraggingFile] = useState(false)
    const previousFileNameRef = useRef(localTemplateFileName)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const dragDepthRef = useRef(0)

    const submitTemplateFile = (file: File) => {
        const input = fileInputRef.current
        if (!input) {
            return
        }

        const dataTransfer = new DataTransfer()
        dataTransfer.items.add(file)
        input.files = dataTransfer.files
        void onLocalTemplateFileUpload({ target: input } as ChangeEvent<HTMLInputElement>)
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

    useEffect(() => {
        const fileNameChanged = localTemplateFileName !== previousFileNameRef.current
        previousFileNameRef.current = localTemplateFileName

        if (inputMode === 'file' && localTemplateFileName && fileNameChanged) {
            setInputMode('visual')
        }
    }, [localTemplateFileName, inputMode])

    return (
        <section className={styles.root}>
            <div>
                <h5 className={styles.title}>Create custom template</h5>
            </div>

            <label className={styles.label}>
                <span className={styles.labelText}>Template title</span>
                <input
                    type="text"
                    value={localTemplateTitle}
                    onChange={(event) => onLocalTemplateTitleChange(event.target.value)}
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
                    <TemplateStructureEditor
                        value={localTemplateJson}
                        onChange={onLocalTemplateJsonChange}
                    />
                ) : (
                    <label
                        className={`${styles.fileDropZone} ${
                            isDraggingFile ? styles.fileDropZoneDragging : ''
                        } ${localTemplateFileName ? styles.fileDropZoneFilled : ''}`}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".json,application/json"
                            onChange={(event) => onLocalTemplateFileUpload(event)}
                            className={styles.hiddenInput}
                        />
                        <span className={styles.fileDropIcon} aria-hidden="true">
                            <i className="fas fa-upload" />
                        </span>
                        <span className={styles.fileDropTitle}>
                            {localTemplateFileName || 'Drop JSON template here'}
                        </span>
                        <span className={styles.fileDropHint}>
                            {localTemplateFileName
                                ? 'Click or drop another file to replace'
                                : 'or click anywhere to browse'}
                        </span>
                    </label>
                )}
            </div>

            <button
                type="button"
                onClick={() => onAddLocalTemplate()}
                disabled={isCreatingTemplate}
                className={`${styles.saveButton} btn btn-primary btn-wide`}
            >
                {isCreatingTemplate ? 'Saving template...' : 'Save template'}
            </button>

            <Alert variant="error">{localTemplateError}</Alert>
        </section>
    )
}
