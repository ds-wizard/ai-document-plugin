import { ChangeEvent } from 'react'

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
        <section className="ai-doc-template-section">
            <div>
                <div className="ai-doc-section-title">Create custom template</div>
                <div className="ai-doc-section-text">
                    Upload or paste template JSON. After saving, the template will be stored in the
                    backend database and appear in the dropdown immediately.
                </div>
            </div>

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">Template title</span>
                <input
                    type="text"
                    value={localTemplateTitle}
                    onChange={(event) => onLocalTemplateTitleChange(event.target.value)}
                    placeholder="My custom DMP template"
                    className="ai-doc-input"
                />
            </label>

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">Template JSON file</span>
                <label className="ai-doc-file-picker">
                    <span className="ai-doc-file-picker-button">Choose file</span>
                    <span
                        className={`ai-doc-file-picker-name ${
                            localTemplateFileName
                                ? 'ai-doc-file-picker-name-filled'
                                : 'ai-doc-file-picker-name-empty'
                        }`}
                    >
                        {localTemplateFileName || 'No file selected'}
                    </span>
                    <input
                        type="file"
                        accept=".json,application/json"
                        onChange={(event) => onLocalTemplateFileUpload(event)}
                        className="ai-doc-hidden-input"
                    />
                </label>
            </label>

            <label className="ai-doc-label">
                <span className="ai-doc-label-text">Template JSON</span>
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
                    className="ai-doc-input ai-doc-template-textarea"
                />
            </label>

            <button
                type="button"
                onClick={() => onAddLocalTemplate()}
                disabled={isCreatingTemplate}
                className="ai-doc-button ai-doc-button-primary"
            >
                {isCreatingTemplate ? 'Saving template...' : 'Save template'}
            </button>

            {localTemplateError ? (
                <div className="ai-doc-alert ai-doc-alert-error">{localTemplateError}</div>
            ) : null}
        </section>
    )
}
