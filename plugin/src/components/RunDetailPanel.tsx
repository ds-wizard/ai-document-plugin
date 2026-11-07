import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Badge } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted, Title } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect } from 'react'

import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import {
    getRunTimeLabel,
    getRunVersionLabel,
    type UseGenerationHistoryResult,
} from '@/hooks/useGenerationHistory'

type RunDetailPanelProps = {
    runId: string
    history: UseGenerationHistoryResult
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
            <Title>{run.templateTitle}</Title>
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
