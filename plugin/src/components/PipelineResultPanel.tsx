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
        <section className="ai-doc-result-panel">
            <div className="ai-doc-result-header">
                <div>
                    <div className="ai-doc-section-title">Pipeline output</div>
                    <div className="ai-doc-result-subtitle">
                        Preview of the generated document. The render mode is prepared for more
                        output formats later.
                    </div>
                </div>

                <div className="ai-doc-segmented-control">
                    {(['formatted', 'raw'] as const).map((mode) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => onResultRenderModeChange(mode)}
                            className={`ai-doc-segmented-button ${
                                resultRenderMode === mode ? 'ai-doc-segmented-button-active' : ''
                            }`}
                        >
                            {mode === 'formatted' ? 'Formatted' : 'Raw'}
                        </button>
                    ))}
                </div>
            </div>

            {displayedResultMarkdown ? (
                <div className="ai-doc-result-actions">
                    <button
                        type="button"
                        onClick={() => onCopyMarkdown()}
                        className="ai-doc-button ai-doc-button-pill ai-doc-button-secondary"
                    >
                        Copy markdown
                    </button>

                    <button
                        type="button"
                        onClick={() => onDownloadMarkdown()}
                        className="ai-doc-button ai-doc-button-pill ai-doc-button-secondary"
                    >
                        Download .md
                    </button>

                    <button
                        type="button"
                        onClick={() => onSaveEditedVersion()}
                        disabled={!hasResultChanges || isSavingEditedVersion}
                        className="ai-doc-button ai-doc-button-pill ai-doc-button-success"
                    >
                        {isSavingEditedVersion ? 'Saving...' : 'Save edited version'}
                    </button>
                </div>
            ) : null}

            <div className="ai-doc-result-body">
                {!resultMarkdown ? (
                    <div className="ai-doc-result-empty">
                        The generated markdown will appear here after a successful pipeline run.
                    </div>
                ) : resultRenderMode === 'raw' ? (
                    <textarea
                        value={editableResultMarkdown}
                        onChange={(event) => onEditableResultMarkdownChange(event.target.value)}
                        className="ai-doc-result-textarea"
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
