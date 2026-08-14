import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { exportPipelineResultAsDocx, saveEditedPipelineResult } from '@/client'
import styles from '@/components/PipelineResultPanel.module.css'
import { MarkdownRenderer } from '@/markdown-utils'
import type { PipelineStatusResponse, ResultRenderMode } from '@/types'

const triggerBlobDownload = (blob: Blob, fileName: string) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
}

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
    const [isDownloadingDocx, setIsDownloadingDocx] = useState(false)

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

    const onDownloadMarkdown = () => {
        if (!displayedResultMarkdown) {
            return
        }

        const blob = new Blob([displayedResultMarkdown], { type: 'text/markdown;charset=utf-8' })
        triggerBlobDownload(blob, `${downloadBaseName || 'pipeline-output'}.md`)
        toast.success('Markdown download has started.')
    }

    const onDownloadDocx = async () => {
        if (!displayedResultMarkdown || !resultRunId) {
            toast.error('There is no pipeline result to export yet.')
            return
        }

        setIsDownloadingDocx(true)
        try {
            // The editor's current text is sent along, so unsaved edits are exported too.
            const blob = await exportPipelineResultAsDocx(resultRunId, displayedResultMarkdown)
            triggerBlobDownload(blob, `${downloadBaseName || 'pipeline-output'}.docx`)
            toast.success('Word download has started.')
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : 'Failed to export the result as a Word document.',
            )
        } finally {
            setIsDownloadingDocx(false)
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
                                onClick={() => void onDownloadDocx()}
                                disabled={!resultRunId || isDownloadingDocx}
                                className="btn btn-outline-secondary"
                            >
                                {isDownloadingDocx ? 'Preparing...' : 'Download .docx'}
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
