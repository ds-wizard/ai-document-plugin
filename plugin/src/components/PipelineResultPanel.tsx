import { MarkdownRenderer } from '@/markdown-utils'
import type { ResultRenderMode } from '@/types'

type PipelineResultPanelProps = {
    resultMarkdown: string | null
    editableResultMarkdown: string
    resultRenderMode: ResultRenderMode
    isSavingEditedVersion: boolean
    hasResultChanges: boolean
    displayedResultMarkdown: string | null
    onResultRenderModeChange: (mode: ResultRenderMode) => void
    onEditableResultMarkdownChange: (value: string) => void
    onCopyMarkdown: () => void
    onDownloadMarkdown: () => void
    onSaveEditedVersion: () => void
}

export function PipelineResultPanel({
    resultMarkdown,
    editableResultMarkdown,
    resultRenderMode,
    isSavingEditedVersion,
    hasResultChanges,
    displayedResultMarkdown,
    onResultRenderModeChange,
    onEditableResultMarkdownChange,
    onCopyMarkdown,
    onDownloadMarkdown,
    onSaveEditedVersion,
}: PipelineResultPanelProps) {
    return (
        <section
            style={{
                display: 'grid',
                gap: '0.75rem',
                marginTop: '0.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid #e2e8f0',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '1rem',
                    flexWrap: 'wrap',
                }}
            >
                <div>
                    <div style={{ fontWeight: 700 }}>Pipeline output</div>
                    <div style={{ color: '#64748b', fontSize: '0.95rem' }}>
                        Preview of the generated document. The render mode is prepared for more
                        output formats later.
                    </div>
                </div>

                <div
                    style={{
                        display: 'inline-flex',
                        border: '1px solid #cbd5e1',
                        borderRadius: '999px',
                        overflow: 'hidden',
                        background: '#fff',
                    }}
                >
                    {(['formatted', 'raw'] as const).map((mode) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => onResultRenderModeChange(mode)}
                            style={{
                                border: 0,
                                padding: '0.55rem 0.9rem',
                                background: resultRenderMode === mode ? '#0f172a' : 'transparent',
                                color: resultRenderMode === mode ? '#fff' : '#334155',
                                cursor: 'pointer',
                                fontWeight: 600,
                            }}
                        >
                            {mode === 'formatted' ? 'Formatted' : 'Raw'}
                        </button>
                    ))}
                </div>
            </div>

            {displayedResultMarkdown ? (
                <div
                    style={{
                        display: 'flex',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                    }}
                >
                    <button
                        type="button"
                        onClick={() => onCopyMarkdown()}
                        style={{
                            padding: '0.65rem 0.9rem',
                            borderRadius: '999px',
                            border: '1px solid #cbd5e1',
                            background: '#fff',
                            color: '#0f172a',
                            cursor: 'pointer',
                            fontWeight: 600,
                        }}
                    >
                        Copy markdown
                    </button>

                    <button
                        type="button"
                        onClick={() => onDownloadMarkdown()}
                        style={{
                            padding: '0.65rem 0.9rem',
                            borderRadius: '999px',
                            border: '1px solid #cbd5e1',
                            background: '#fff',
                            color: '#0f172a',
                            cursor: 'pointer',
                            fontWeight: 600,
                        }}
                    >
                        Download .md
                    </button>

                    <button
                        type="button"
                        onClick={() => onSaveEditedVersion()}
                        disabled={!hasResultChanges || isSavingEditedVersion}
                        style={{
                            padding: '0.65rem 0.9rem',
                            borderRadius: '999px',
                            border: 0,
                            background:
                                !hasResultChanges || isSavingEditedVersion ? '#94a3b8' : '#0f766e',
                            color: '#fff',
                            cursor:
                                !hasResultChanges || isSavingEditedVersion
                                    ? 'not-allowed'
                                    : 'pointer',
                            fontWeight: 600,
                        }}
                    >
                        {isSavingEditedVersion ? 'Saving...' : 'Save edited version'}
                    </button>
                </div>
            ) : null}

            <div
                style={{
                    minHeight: '14rem',
                    padding: '1rem',
                    borderRadius: '1rem',
                    border: '1px solid #cbd5e1',
                    background: '#f8fafc',
                    display: 'grid',
                    gap: '1rem',
                }}
            >
                {!resultMarkdown ? (
                    <div style={{ color: '#64748b', lineHeight: 1.6 }}>
                        The generated markdown will appear here after a successful pipeline run.
                    </div>
                ) : resultRenderMode === 'raw' ? (
                    <textarea
                        value={editableResultMarkdown}
                        onChange={(event) => onEditableResultMarkdownChange(event.target.value)}
                        style={{
                            margin: 0,
                            color: '#0f172a',
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                            width: '100%',
                            minHeight: '20rem',
                            resize: 'vertical',
                            border: '1px solid #cbd5e1',
                            borderRadius: '0.75rem',
                            padding: '1rem',
                            background: '#fff',
                            lineHeight: 1.6,
                        }}
                    >
                        {editableResultMarkdown}
                    </textarea>
                ) : (
                    <MarkdownRenderer markdown={displayedResultMarkdown || ''} />
                )}
            </div>
        </section>
    )
}
