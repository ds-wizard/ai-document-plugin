import { ChangeEvent } from 'react'

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
    return (
        <section className={styles.root}>
            <div>
                <h5 className={styles.title}>Create custom template</h5>
                <div className={styles.text}>
                    Build a template structure or upload JSON. After saving, the template will be
                    stored in the backend database and appear in the dropdown immediately.
                </div>
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

            <label className={styles.label}>
                <span className={styles.labelText}>Template JSON file</span>
                <label className={styles.filePicker}>
                    <span className={styles.filePickerButton}>Choose file</span>
                    <span
                        className={`${styles.fileName} ${
                            localTemplateFileName ? styles.fileNameFilled : styles.fileNameEmpty
                        }`}
                    >
                        {localTemplateFileName || 'No file selected'}
                    </span>
                    <input
                        type="file"
                        accept=".json,application/json"
                        onChange={(event) => onLocalTemplateFileUpload(event)}
                        className={styles.hiddenInput}
                    />
                </label>
            </label>

            <div className={styles.label}>
                <span className={styles.labelText}>Template structure</span>
                <TemplateStructureEditor
                    value={localTemplateJson}
                    onChange={onLocalTemplateJsonChange}
                />
            </div>

            <button
                type="button"
                onClick={() => onAddLocalTemplate()}
                disabled={isCreatingTemplate}
                className={`${styles.saveButton} btn btn-primary btn-wide`}
            >
                {isCreatingTemplate ? 'Saving template...' : 'Save template'}
            </button>

            {localTemplateError ? <div className={styles.alert}>{localTemplateError}</div> : null}
        </section>
    )
}
