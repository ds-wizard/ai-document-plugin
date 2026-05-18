import styles from '@/components/PipelineResultPanel.module.css'
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
        <section className={styles.root}>
            <div className={styles.header}>
                <div className={styles.headerContent}>
                    <h4>Pipeline output</h4>
                    <div className={styles.subtitle}>
                        Preview of the generated document. The render mode is prepared for more
                        output formats later.
                    </div>
                </div>
                <div className={styles.toolbar}>
                    <div className={`${styles.segmentedControl} btn-group`} role="group">
                        {(
                            [
                                {
                                    mode: 'formatted' as const,
                                    label: 'Formatted',
                                    dataCy: 'dt-editor_preview-mode_project',
                                },
                                {
                                    mode: 'raw' as const,
                                    label: 'Raw',
                                    dataCy: 'dt-editor_preview-mode_km-editor',
                                },
                            ] as const
                        ).map(({ mode, label, dataCy }) => (
                            <button
                                key={mode}
                                type="button"
                                onClick={() => onResultRenderModeChange(mode)}
                                className={
                                    resultRenderMode === mode
                                        ? 'btn btn-primary'
                                        : 'btn btn-outline-primary'
                                }
                                data-cy={dataCy}
                            >
                                {label}
                            </button>
                        ))}
                    </div>

                    {displayedResultMarkdown ? (
                        <div className={styles.actions}>
                            <button
                                type="button"
                                onClick={() => onCopyMarkdown()}
                                className="btn btn-outline-secondary"
                            >
                                Copy markdown
                            </button>

                            <button
                                type="button"
                                onClick={() => onDownloadMarkdown()}
                                className="btn btn-outline-secondary"
                            >
                                Download .md
                            </button>

                            <button
                                type="button"
                                onClick={() => onSaveEditedVersion()}
                                disabled={!hasResultChanges || isSavingEditedVersion}
                                className={`btn btn-outline-secondary ${styles.saveButton}`}
                            >
                                {isSavingEditedVersion ? 'Saving...' : 'Save edited version'}
                            </button>
                        </div>
                    ) : null}
                </div>
            </div>

            <div className={styles.body}>
                {!resultMarkdown ? (
                    <div className={styles.empty}>
                        The generated markdown will appear here after a successful pipeline run.
                    </div>
                ) : resultRenderMode === 'raw' ? (
                    <textarea
                        value={editableResultMarkdown}
                        onChange={(event) => onEditableResultMarkdownChange(event.target.value)}
                        className={styles.textarea}
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
