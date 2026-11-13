import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Badge } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect } from 'react'

import { PipelineResultPanel } from '@/components/PipelineResultPanel'
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

function RunNameEditor({
    name,
    onRename,
}: {
    name: string
    onRename: (name: string) => Promise<boolean>
}) {
    const [isEditing, setIsEditing] = useState(false)
    const [draft, setDraft] = useState(name)
    const [isSaving, setIsSaving] = useState(false)

    if (isEditing) {
        return (
            <form
                className={styles.titleRow}
                onSubmit={async (event) => {
                    event.preventDefault()
                    if (!draft.trim() || isSaving) return
                    setIsSaving(true)
                    try {
                        if (await onRename(draft)) setIsEditing(false)
                    } finally {
                        setIsSaving(false)
                    }
                }}
                onKeyDown={(event) => {
                    if (event.key === 'Escape' && !isSaving) {
                        event.preventDefault()
                        setIsEditing(false)
                    }
                }}
            >
                <input
                    className={`form-control ${styles.nameInput}`}
                    aria-label="Run name"
                    value={draft}
                    disabled={isSaving}
                    onChange={(event) => setDraft(event.target.value)}
                    autoFocus
                />
                <button
                    className="btn btn-primary btn-sm"
                    type="submit"
                    disabled={!draft.trim() || isSaving}
                >
                    {isSaving ? 'Saving...' : 'Apply'}
                </button>
                <button
                    className="btn btn-outline-secondary btn-sm"
                    type="button"
                    disabled={isSaving}
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
                className={styles.renameButton}
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
        return <AsyncBlock loading loadingLabel="Loading generation..." />
    }

    const heading = (
        <Stack>
            <RunNameEditor
                key={runId}
                name={getRunTitle(run)}
                onRename={(name) => history.renameRun(runId, name)}
            />
            <Inline>
                <Badge>{getRunVersionLabel(run)}</Badge>
                <Muted>{getRunTimeLabel(run)}</Muted>
            </Inline>
        </Stack>
    )

    if (run.status === 'queued' || run.status === 'running') {
        return (
            <Stack loose>
                {heading}
                <AsyncBlock
                    loading
                    loadingLabel={
                        run.progressMessage ||
                        (run.status === 'queued'
                            ? 'Waiting in the queue...'
                            : 'Generating document...')
                    }
                />
            </Stack>
        )
    }

    if (run.status === 'cancelled') {
        return (
            <div className={styles.root}>
                {heading}
                <div className={styles.progress}>
                    <i className="fas fa-ban" aria-hidden="true" />
                    Pipeline cancelled.
                </div>
            </div>
        )
    }

    if (run.status === 'failed') {
        return (
            <Stack loose>
                {heading}
                <Alert tone="danger">{run.error?.message || 'Pipeline generation failed.'}</Alert>
            </Stack>
        )
    }

    if (!run.hasDetail) {
        return (
            <Stack loose>
                {heading}
                <AsyncBlock loading loadingLabel="Loading generated document..." />
            </Stack>
        )
    }

    return (
        <Stack loose>
            {heading}
            <PipelineResultPanel
                resultMarkdown={run.resultMarkdown}
                resultRunId={run.runId}
                downloadBaseName={run.templateTitle}
                onSaved={applyStatus}
            />
        </Stack>
    )
}
