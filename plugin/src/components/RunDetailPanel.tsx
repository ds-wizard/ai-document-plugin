import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Badge } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Button, IconButton, SubmitButton } from '@ds-wizard/plugin-sdk/ui/Button'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted, Title } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect, useState } from 'react'

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
                    className={`ui-input ${styles.nameInput}`}
                    aria-label="Run name"
                    value={draft}
                    disabled={isSaving}
                    onChange={(event) => setDraft(event.target.value)}
                    autoFocus
                />
                <SubmitButton
                    variant="primary"
                    size="small"
                    loading={isSaving}
                    disabled={!draft.trim() || isSaving}
                >
                    {isSaving ? 'Saving...' : 'Apply'}
                </SubmitButton>
                <Button size="small" disabled={isSaving} onClick={() => setIsEditing(false)}>
                    Cancel
                </Button>
            </form>
        )
    }

    return (
        <div className={styles.titleRow}>
            <Title className={styles.name}>{name}</Title>
            <IconButton
                icon="fa-pen"
                label="Rename run"
                quiet
                tooltip
                onClick={() => {
                    setDraft(name)
                    setIsEditing(true)
                }}
            />
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
            <Stack loose>
                {heading}
                <Alert tone="info">Pipeline cancelled.</Alert>
            </Stack>
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
