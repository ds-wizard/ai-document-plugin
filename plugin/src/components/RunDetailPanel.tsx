import { useEffect, useState } from 'react'

import { FeedbackAlert } from '@/components/FeedbackAlert'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import styles from '@/components/RunDetailPanel.module.css'
import {
    getRunTimeLabel,
    getRunTitle,
    getRunVersionLabel,
    type UseGenerationHistoryResult,
} from '@/hooks/useGenerationHistory'

type RunDetailPanelProps = {
    runId: string
    history: UseGenerationHistoryResult
}

function RunNameEditor({ name, onRename }: { name: string; onRename: (name: string) => void }) {
    const [isEditing, setIsEditing] = useState(false)
    const [draft, setDraft] = useState(name)

    if (isEditing) {
        return (
            <form
                className={styles.titleRow}
                onSubmit={(event) => {
                    event.preventDefault()
                    if (!draft.trim()) return
                    onRename(draft)
                    setIsEditing(false)
                }}
                onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                        event.preventDefault()
                        setIsEditing(false)
                    }
                }}
            >
                <input
                    className={`form-control ${styles.nameInput}`}
                    aria-label="Run name"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    autoFocus
                />
                <button className="btn btn-primary btn-sm" type="submit" disabled={!draft.trim()}>
                    Apply
                </button>
                <button
                    className="btn btn-outline-secondary btn-sm"
                    type="button"
                    onClick={() => setIsEditing(false)}
                >
                    Cancel
                </button>
            </form>
        )
    }

    return (
        <div className={styles.titleRow}>
            <h4>{name}</h4>
            <button
                className="btn btn-outline-secondary btn-sm"
                type="button"
                aria-label="Rename run"
                title="Rename run"
                onClick={() => {
                    setDraft(name)
                    setIsEditing(true)
                }}
            >
                <i className="fas fa-pencil-alt" aria-hidden="true" />
            </button>
        </div>
    )
}

export function RunDetailPanel({ runId, history }: RunDetailPanelProps) {
    const run = history.getRun(runId)
    const { ensureDetailLoaded, applyStatus } = history

    useEffect(() => {
        if (run?.status === 'succeeded' && !run.hasDetail) {
            ensureDetailLoaded(runId)
        }
    }, [runId, run?.status, run?.hasDetail, ensureDetailLoaded])

    if (!run) {
        return (
            <div className={styles.root}>
                <div className={styles.progress}>
                    <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                    Loading generation...
                </div>
            </div>
        )
    }

    const heading = (
        <header className={styles.heading}>
            <RunNameEditor
                key={runId}
                name={getRunTitle(run)}
                onRename={(name) => history.renameRun(runId, name)}
            />
            <div className={styles.metadata}>
                <span className={`badge bg-secondary ${styles.versionBadge}`}>
                    {getRunVersionLabel(run)}
                </span>
                <span>{getRunTimeLabel(run)}</span>
            </div>
        </header>
    )

    if (run.status === 'queued' || run.status === 'running') {
        return (
            <div className={styles.root}>
                {heading}
                <div className={styles.progress}>
                    <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                    {run.progressMessage ||
                        (run.status === 'queued'
                            ? 'Waiting in the queue...'
                            : 'Generating document...')}
                </div>
            </div>
        )
    }

    if (run.status === 'failed') {
        return (
            <div className={styles.root}>
                {heading}
                <FeedbackAlert kind="error">
                    {run.error?.message || 'Pipeline generation failed.'}
                </FeedbackAlert>
            </div>
        )
    }

    if (!run.hasDetail) {
        return (
            <div className={styles.root}>
                {heading}
                <div className={styles.progress}>
                    <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                    Loading generated document...
                </div>
            </div>
        )
    }

    return (
        <div className={styles.root}>
            {heading}
            <PipelineResultPanel
                resultMarkdown={run.resultMarkdown}
                resultRunId={run.runId}
                downloadBaseName={run.templateTitle}
                onSaved={applyStatus}
            />
        </div>
    )
}
