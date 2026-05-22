import { ChangeEvent } from 'react'

import styles from '@/components/CustomTemplateSection.module.css'

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
                    Upload or paste template JSON. After saving, the template will be stored in the
                    backend database and appear in the dropdown immediately.
                </div>
            </div>

            <label className={styles.label}>
                <span className={styles.labelText}>Template title</span>
                <input
                    type="text"
                    value={localTemplateTitle}
                    onChange={(event) => onLocalTemplateTitleChange(event.target.value)}
                    placeholder="My custom DMP template"
                    className={styles.input}
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

            <label className={styles.label}>
                <span className={styles.labelText}>Template JSON</span>
                <textarea
                    value={localTemplateJson}
                    onChange={(event) => onLocalTemplateJsonChange(event.target.value)}
                    placeholder={`{
  "sections": [
    {
      "title": "...",
      "sections": [
        {
          "title": "...",
          "content": "..."
        }
      ]
    }
  ]
}`}
                    className={`${styles.input} ${styles.textarea}`}
                />
            </label>

            <button
                type="button"
                onClick={() => onAddLocalTemplate()}
                disabled={isCreatingTemplate}
                className="btn btn-primary btn-wide"
            >
                {isCreatingTemplate ? 'Saving template...' : 'Save template'}
            </button>

            {localTemplateError ? <div className={styles.alert}>{localTemplateError}</div> : null}
        </section>
    )
}
