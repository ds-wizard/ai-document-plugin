import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { saveEditedPipelineResult } from '@/client'
import { DownloadDropdown } from '@/components/DownloadDropdown'
import styles from '@/components/PipelineResultPanel.module.css'
import { MarkdownRenderer } from '@/markdown-utils'
import type { PipelineStatusResponse, ResultRenderMode } from '@/types'

type PipelineResultPanelProps = {
    resultMarkdown: string | null
    resultRunId: string | null
    downloadBaseName: string
    onSaved?: (status: PipelineStatusResponse) => void
}

export function PipelineResultPanel({
    resultMarkdown,
    resultRunId,
    downloadBaseName,
    onSaved,
}: PipelineResultPanelProps) {
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [committedMarkdown, setCommittedMarkdown] = useState<string | null>(null)
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [isSavingEditedVersion, setIsSavingEditedVersion] = useState(false)

    useEffect(() => {
        setEditableResultMarkdown(resultMarkdown ?? '')
        setCommittedMarkdown(resultMarkdown)
    }, [resultMarkdown])

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges =
        resultMarkdown !== null && editableResultMarkdown !== (committedMarkdown ?? '')

    const onCopyMarkdown = async () => {
        if (!displayedResultMarkdown) {
            return
        }

        try {
            await navigator.clipboard.writeText(displayedResultMarkdown)
            toast.success('Markdown has been copied to the clipboard.')
        } catch {
            toast.error('Failed to copy markdown to the clipboard.')
        }
    }

    const onSaveEditedVersion = async () => {
        if (!resultRunId || !resultMarkdown) {
            toast.error('There is no pipeline result to save yet.')
            return
        }

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(resultRunId, editableResultMarkdown)

            const savedMarkdown = data.resultMarkdown ?? editableResultMarkdown
            setCommittedMarkdown(savedMarkdown)
            setEditableResultMarkdown(savedMarkdown)
            onSaved?.(data)
            toast.success('Edited markdown has been saved.')
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : 'Failed to save the edited version.',
            )
        } finally {
            setIsSavingEditedVersion(false)
        }
    }

    return (
        <section className={styles.root}>
            <div className={styles.header}>
                <div className={styles.toolbar}>
                    <div className="ai-doc-segmented-control btn-group" role="group">
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
                                onClick={() => setResultRenderMode(mode)}
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
                                onClick={() => void onCopyMarkdown()}
                                className="btn btn-outline-secondary"
                            >
                                <i
                                    className={`fas fa-copy ${styles.buttonIcon}`}
                                    aria-hidden="true"
                                />
                                Copy markdown
                            </button>

                            <DownloadDropdown
                                markdown={displayedResultMarkdown}
                                runId={resultRunId}
                                baseName={downloadBaseName}
                            />
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
                    <div className={styles.rawEditor}>
                        <div className={styles.rawToolbar}>
                            <button
                                type="button"
                                onClick={() => void onSaveEditedVersion()}
                                disabled={!hasResultChanges || isSavingEditedVersion}
                                className={`btn btn-outline-secondary ${styles.saveButton}`}
                            >
                                <i
                                    className={`fas fa-save ${styles.buttonIcon}`}
                                    aria-hidden="true"
                                />
                                {isSavingEditedVersion ? 'Saving...' : 'Save'}
                            </button>
                        </div>

                        <textarea
                            value={editableResultMarkdown}
                            onChange={(event) => setEditableResultMarkdown(event.target.value)}
                            className={styles.textarea}
                        />
                    </div>
                ) : (
                    <MarkdownRenderer markdown={displayedResultMarkdown || ''} />
                )}
            </div>
        </section>
    )
}
