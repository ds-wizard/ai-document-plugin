import { useEffect, useState } from 'react'

import { getPipelineStatus, saveEditedPipelineResult } from '@/client'
import styles from '@/components/ExportView.module.css'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import type { PipelineStatusResponse, ResultRenderMode } from '@/types'

type ExportStatus = 'polling' | 'succeeded' | 'failed'

type ExportViewProps = {
    runId: string
    onBack: () => void
    onPipelineSucceeded: (data: PipelineStatusResponse) => void
}

export function ExportView({ runId, onBack, onPipelineSucceeded }: ExportViewProps) {
    const [status, setStatus] = useState<ExportStatus>('polling')
    const [progressMessage, setProgressMessage] = useState<string | null>(null)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [resultMarkdown, setResultMarkdown] = useState<string | null>(null)
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [isSavingEditedVersion, setIsSavingEditedVersion] = useState(false)

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges = resultMarkdown !== null && editableResultMarkdown !== resultMarkdown
    const isPolling = status === 'polling'

    useEffect(() => {
        let isMounted = true
        let intervalId: number | undefined

        const stopPolling = () => {
            if (intervalId !== undefined) {
                window.clearInterval(intervalId)
                intervalId = undefined
            }
        }

        const poll = async () => {
            try {
                const data = await getPipelineStatus(runId)
                if (!isMounted) {
                    return
                }

                if (data.status === 'running') {
                    setProgressMessage(
                        data.progressMessage
                            ? data.progressMessage
                            : `Pipeline is running for the template "${data.templateTitle}".`,
                    )
                    return
                }

                stopPolling()

                if (data.status === 'succeeded') {
                    setStatus('succeeded')
                    setProgressMessage(null)
                    setResultMarkdown(data.resultMarkdown)
                    setEditableResultMarkdown(data.resultMarkdown || '')
                    onPipelineSucceeded(data)
                    setSuccessMessage(
                        `Pipeline has been completed for the template "${data.templateTitle}".`,
                    )
                    return
                }

                setStatus('failed')
                setProgressMessage(null)
                setErrorMessage(
                    data.error
                        ? `Pipeline failed: ${data.error}`
                        : `Pipeline failed for the template "${data.templateTitle}".`,
                )
            } catch (error) {
                if (!isMounted) {
                    return
                }

                stopPolling()
                setStatus('failed')
                setProgressMessage(null)
                setErrorMessage(
                    error instanceof Error ? error.message : 'Unable to determine pipeline status.',
                )
            }
        }

        setStatus('polling')
        setProgressMessage(null)
        setErrorMessage(null)
        setSuccessMessage(null)
        setResultMarkdown(null)
        setEditableResultMarkdown('')

        void poll()
        intervalId = window.setInterval(() => {
            void poll()
        }, 2000)

        return () => {
            isMounted = false
            stopPolling()
        }
    }, [onPipelineSucceeded, runId])

    const handleCopyMarkdown = async () => {
        if (!displayedResultMarkdown) {
            return
        }

        try {
            await navigator.clipboard.writeText(displayedResultMarkdown)
            setErrorMessage(null)
            setSuccessMessage('Markdown has been copied to the clipboard.')
        } catch {
            setErrorMessage('Failed to copy markdown to the clipboard.')
        }
    }

    const handleDownloadMarkdown = () => {
        if (!displayedResultMarkdown) {
            return
        }

        const blob = new Blob([displayedResultMarkdown], { type: 'text/markdown;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${runId}.md`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        setErrorMessage(null)
        setSuccessMessage('Markdown download has started.')
    }

    const handleSaveEditedVersion = async () => {
        if (!resultMarkdown) {
            setErrorMessage('There is no pipeline result to save yet.')
            return
        }

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(runId, editableResultMarkdown)

            setResultMarkdown(data.resultMarkdown)
            setEditableResultMarkdown(data.resultMarkdown || '')
            setErrorMessage(null)
            setSuccessMessage('Edited markdown has been saved.')
        } catch (error) {
            setErrorMessage(
                error instanceof Error ? error.message : 'Failed to save the edited version.',
            )
        } finally {
            setIsSavingEditedVersion(false)
        }
    }

    return (
        <div className={styles.root}>
            <header className={styles.header}>
                <button type="button" onClick={onBack} className={styles.backButton}>
                    <span className={styles.backIcon} aria-hidden="true">
                        ←
                    </span>
                    Back
                </button>
                <h2 className={styles.title}>Export result</h2>
            </header>

            {isPolling ? (
                <div className={styles.loading}>{progressMessage || 'Loading export...'}</div>
            ) : null}

            {errorMessage ? (
                <div className={`${styles.alert} ${styles.errorAlert}`}>{errorMessage}</div>
            ) : null}

            {successMessage ? (
                <div className={`${styles.alert} ${styles.successAlert}`}>{successMessage}</div>
            ) : null}

            {!isPolling ? (
                <PipelineResultPanel
                    resultMarkdown={resultMarkdown}
                    editableResultMarkdown={editableResultMarkdown}
                    resultRenderMode={resultRenderMode}
                    isSavingEditedVersion={isSavingEditedVersion}
                    hasResultChanges={hasResultChanges}
                    displayedResultMarkdown={displayedResultMarkdown}
                    onResultRenderModeChange={setResultRenderMode}
                    onEditableResultMarkdownChange={setEditableResultMarkdown}
                    onCopyMarkdown={() => void handleCopyMarkdown()}
                    onDownloadMarkdown={handleDownloadMarkdown}
                    onSaveEditedVersion={() => void handleSaveEditedVersion()}
                />
            ) : null}
        </div>
    )
}
