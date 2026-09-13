import { getPipelineStatus } from '@/client'
import type { PipelineStatusResponse } from '@/types'

const DEFAULT_POLL_INTERVAL_MS = 10_000

type PollRunStatusCallbacks = {
    onUpdate: (status: PipelineStatusResponse) => void
    onSettle?: (status: PipelineStatusResponse) => void
    onError?: (error: unknown) => void
}

/**
 * Polls a single run's status until it settles (succeeded/failed), then stops on its
 * own. Framework-free: no React, no knowledge of any store — just one run, one loop.
 * Returns a `stop()` that cancels any pending fetch/timeout immediately.
 */
export function pollRunStatus(
    runId: string,
    { onUpdate, onSettle, onError }: PollRunStatusCallbacks,
    intervalMs = DEFAULT_POLL_INTERVAL_MS,
): () => void {
    let cancelled = false
    let timeoutId: ReturnType<typeof window.setTimeout> | undefined

    const tick = async () => {
        try {
            const status = await getPipelineStatus(runId)
            if (cancelled) {
                return
            }

            onUpdate(status)

            if (status.status === 'succeeded' || status.status === 'failed') {
                onSettle?.(status)
                return
            }

            timeoutId = window.setTimeout(() => {
                void tick()
            }, intervalMs)
        } catch (error) {
            if (!cancelled) {
                onError?.(error)
            }
        }
    }

    void tick()

    return () => {
        cancelled = true
        if (timeoutId !== undefined) {
            window.clearTimeout(timeoutId)
            timeoutId = undefined
        }
    }
}
