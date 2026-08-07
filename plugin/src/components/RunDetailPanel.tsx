import { useEffect } from 'react'

import { FeedbackAlert } from '@/components/FeedbackAlert'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import styles from '@/components/RunDetailPanel.module.css'
import type { FeedbackController } from '@/hooks/useFeedback'
import type { UseGenerationHistoryResult } from '@/hooks/useGenerationHistory'

type RunDetailPanelProps = {
    runId: string
    history: UseGenerationHistoryResult
    feedback: FeedbackController
}

export function RunDetailPanel({ runId, history, feedback }: RunDetailPanelProps) {
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

    if (run.status === 'queued' || run.status === 'running') {
        return (
            <div className={styles.root}>
                <h4>{run.templateTitle}</h4>
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
                <h4>{run.templateTitle}</h4>
                <FeedbackAlert kind="error">
                    {run.error?.message || 'Pipeline generation failed.'}
                </FeedbackAlert>
            </div>
        )
    }

    if (!run.hasDetail) {
        return (
            <div className={styles.root}>
                <h4>{run.templateTitle}</h4>
                <div className={styles.progress}>
                    <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                    Loading generated document...
                </div>
            </div>
        )
    }

    return (
        <div className={styles.root}>
            <h4>{run.templateTitle}</h4>
            <PipelineResultPanel
                resultMarkdown={run.resultMarkdown}
                resultRunId={run.runId}
                feedback={feedback}
                downloadBaseName={run.templateTitle}
                onSaved={applyStatus}
            />
        </div>
    )
}
