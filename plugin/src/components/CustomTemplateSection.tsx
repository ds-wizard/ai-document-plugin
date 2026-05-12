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
        <section
            style={{
                display: 'grid',
                gap: '0.75rem',
                padding: '1rem',
                borderRadius: '1rem',
                border: '1px solid #e2e8f0',
                background: '#f8fafc',
            }}
        >
            <div>
                <div style={{ fontWeight: 700 }}>Create custom template</div>
                <div style={{ color: '#64748b', fontSize: '0.95rem', lineHeight: 1.6 }}>
                    Upload or paste template JSON. After saving, the template will be stored in the
                    backend database and appear in the dropdown immediately.
                </div>
            </div>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Template title</span>
                <input
                    type="text"
                    value={localTemplateTitle}
                    onChange={(event) => onLocalTemplateTitleChange(event.target.value)}
                    placeholder="My custom DMP template"
                    style={{
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                    }}
                />
            </label>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Template JSON file</span>
                <label
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                        cursor: 'pointer',
                    }}
                >
                    <span
                        style={{
                            padding: '0.45rem 0.75rem',
                            borderRadius: '999px',
                            background: '#e2e8f0',
                            color: '#0f172a',
                            fontWeight: 600,
                            whiteSpace: 'nowrap',
                        }}
                    >
                        Choose file
                    </span>
                    <span
                        style={{
                            color: localTemplateFileName ? '#0f172a' : '#64748b',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {localTemplateFileName || 'No file selected'}
                    </span>
                    <input
                        type="file"
                        accept=".json,application/json"
                        onChange={(event) => onLocalTemplateFileUpload(event)}
                        style={{ display: 'none' }}
                    />
                </label>
            </label>

            <label style={{ display: 'grid', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>Template JSON</span>
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
                    style={{
                        minHeight: '14rem',
                        padding: '0.75rem',
                        borderRadius: '0.75rem',
                        border: '1px solid #cbd5e1',
                        background: '#fff',
                        resize: 'vertical',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        lineHeight: 1.5,
                    }}
                />
            </label>

            <button
                type="button"
                onClick={() => onAddLocalTemplate()}
                disabled={isCreatingTemplate}
                style={{
                    width: 'fit-content',
                    padding: '0.75rem 1rem',
                    border: 0,
                    borderRadius: '999px',
                    background: isCreatingTemplate ? '#94a3b8' : '#1d4ed8',
                    color: '#fff',
                    cursor: isCreatingTemplate ? 'wait' : 'pointer',
                    fontWeight: 600,
                }}
            >
                {isCreatingTemplate ? 'Saving template...' : 'Save template'}
            </button>

            {localTemplateError ? (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        borderRadius: '0.5rem',
                        background: '#fef2f2',
                        color: '#b91c1c',
                    }}
                >
                    {localTemplateError}
                </div>
            ) : null}
        </section>
    )
}
