import { useEffect, useState } from 'react'

import { saveEditedPipelineResult } from '@/client'
import styles from '@/components/PipelineResultPanel.module.css'
import type { FeedbackController } from '@/hooks/useFeedback'
import { MarkdownRenderer } from '@/markdown-utils'
import type { ResultRenderMode } from '@/types'

type PipelineResultPanelProps = {
    resultMarkdown: string | null
    resultRunId: string | null
    feedback: FeedbackController
    downloadBaseName: string
}

export function PipelineResultPanel({
    resultMarkdown,
    resultRunId,
    feedback,
    downloadBaseName,
}: PipelineResultPanelProps) {
    const { notifyError, notifySuccess } = feedback

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
            notifySuccess('Markdown has been copied to the clipboard.')
        } catch {
            notifyError('Failed to copy markdown to the clipboard.')
        }
    }

    const onDownloadMarkdown = () => {
        if (!displayedResultMarkdown) {
            return
        }

        const blob = new Blob([displayedResultMarkdown], { type: 'text/markdown;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${downloadBaseName || 'pipeline-output'}.md`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        notifySuccess('Markdown download has started.')
    }

    const onSaveEditedVersion = async () => {
        if (!resultRunId || !resultMarkdown) {
            notifyError('There is no pipeline result to save yet.')
            return
        }

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(resultRunId, editableResultMarkdown)

            const savedMarkdown = data.resultMarkdown ?? editableResultMarkdown
            setCommittedMarkdown(savedMarkdown)
            setEditableResultMarkdown(savedMarkdown)
            notifySuccess('Edited markdown has been saved.')
        } catch (error) {
            notifyError(error instanceof Error ? error.message : 'Failed to save the edited version.')
        } finally {
            setIsSavingEditedVersion(false)
        }
    }

    return (
        <section className={styles.root}>
            <div className={styles.header}>
                <div className={styles.headerContent}>
                    <h4>Pipeline output</h4>
                    <div className={styles.subtitle}>Preview of the generated document.</div>
                </div>
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
                                Copy markdown
                            </button>

                            <button
                                type="button"
                                onClick={onDownloadMarkdown}
                                className="btn btn-outline-secondary"
                            >
                                Download .md
                            </button>

                            <button
                                type="button"
                                onClick={() => void onSaveEditedVersion()}
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
                        onChange={(event) => setEditableResultMarkdown(event.target.value)}
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
