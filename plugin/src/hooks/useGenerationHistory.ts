import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import {
    cancelPipeline,
    deletePipeline,
    getPipelineHistory,
    getPipelineStatus,
    runPipeline,
} from '@/client'
import { pollRunStatus } from '@/runPoller'
import type { PipelineErrorResponse, PipelineStatusResponse, PipelineSummaryItem } from '@/types'

type PipelineProject =
    | {
          uuid: string
      }
    | null
    | undefined

export type RunStatusValue = PipelineStatusResponse['status']

export type RunRecord = {
    runId: string
    templateUuid: string
    status: RunStatusValue
    templateTitle: string
    error: PipelineErrorResponse | null
    progressMessage: string | null
    createdAt: string
    updatedAt: string
    namedVersion: string | null
    resultMarkdown: string | null
    /** false = came only from the summary list, never polled/backfilled with full detail. */
    hasDetail: boolean
}

export const getRunVersionLabel = (run: RunRecord): string =>
    run.namedVersion?.trim() || 'Unknown version'

export const getRunTimeLabel = (run: RunRecord): string => {
    const date = new Date(run.createdAt)
    if (Number.isNaN(date.getTime())) return 'Time unavailable'
    const dateLabel = date.toLocaleDateString(undefined, { dateStyle: 'short' })
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${dateLabel}, ${hours}:${minutes}:${seconds}`
}

export type UseGenerationHistoryResult = {
    items: RunRecord[]
    isLoading: boolean
    isStarting: boolean
    hasActiveRun: (templateUuid: string) => boolean
    deletingRunIds: ReadonlySet<string>
    deleteRun: (runId: string) => Promise<boolean>
    cancellingRunIds: ReadonlySet<string>
    cancelRun: (runId: string) => Promise<void>
    // returns a reference to a generation run.
    // This helps with handling live updates from the pollers without need to do subscribe logic
    getRun: (runId: string) => RunRecord | undefined
    startRun: (templateUuid: string, language: string) => Promise<RunRecord | null>
    ensureDetailLoaded: (runId: string) => void
    applyStatus: (status: PipelineStatusResponse) => RunRecord
}

const summaryToRunRecord = (item: PipelineSummaryItem): RunRecord => ({
    runId: item.runId,
    templateUuid: item.templateUuid,
    status: item.status,
    templateTitle: item.templateTitle,
    error: item.error,
    progressMessage: item.progressMessage,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
    namedVersion: item.namedVersion,
    resultMarkdown: null,
    hasDetail: false,
})

const isSettled = (status: RunStatusValue): boolean =>
    status === 'succeeded' || status === 'failed' || status === 'cancelled'

/**
 * Owns every run belonging to the project: the initial history load, starting new
 * runs, and polling in-progress ones. Exactly one poller exists per in-progress run,
 * started once (at load or right after `startRun`) and stopped once it settles.
 * The sidebar and the detail view both read the same `RunRecord`s from here, so they
 * can never disagree with each other.
 */
export function useGenerationHistory(project: PipelineProject): UseGenerationHistoryResult {
    const [runs, setRuns] = useState<Record<string, RunRecord>>({})
    const [isLoading, setIsLoading] = useState(false)
    const [isStarting, setIsStarting] = useState(false)
    // State redraws the pending Stop buttons; the ref blocks duplicate requests
    // immediately, including clicks before React has rendered the new state.
    const [cancellingRunIds, setCancellingRunIds] = useState<Set<string>>(new Set())
    const cancellingRef = useRef(new Set<string>())
    const [deletingRunIds, setDeletingRunIds] = useState<Set<string>>(new Set())
    const deletingRef = useRef(new Set<string>())
    // Ignore requests started before a successful deletion (history, detail, or polling).
    const deletedRunIdsRef = useRef(new Set<string>())

    // Mirrors `runs` synchronously so callbacks (applyStatus, getRun, startRun) can
    // read/merge the latest state without waiting on React's async setState.
    const runsRef = useRef<Record<string, RunRecord>>({})
    const pollersRef = useRef<Map<string, () => void>>(new Map())

    const setRunRecord = useCallback((record: RunRecord) => {
        if (deletedRunIdsRef.current.has(record.runId)) return
        runsRef.current = { ...runsRef.current, [record.runId]: record }
        setRuns(runsRef.current)
    }, [])

    const applyStatus = useCallback(
        (status: PipelineStatusResponse): RunRecord => {
            const record: RunRecord = {
                runId: status.runId,
                templateUuid: status.templateUuid,
                status: status.status,
                templateTitle: status.templateTitle,
                error: status.error,
                createdAt: status.createdAt,
                namedVersion: status.namedVersion,
                updatedAt: status.updatedAt,
                progressMessage: status.progressMessage,
                resultMarkdown: status.resultMarkdown,
                hasDetail: true,
            }
            setRunRecord(record)
            return record
        },
        [setRunRecord],
    )

    const beginPolling = useCallback(
        (runId: string) => {
            if (pollersRef.current.has(runId)) {
                return
            }

            const stop = pollRunStatus(runId, {
                onUpdate: applyStatus,
                onSettle: () => {
                    pollersRef.current.delete(runId)
                },
                onError: () => {
                    // Leave the run at its last known status; this run's poller simply
                    // stops rather than retrying forever.
                    pollersRef.current.delete(runId)
                },
            })
            pollersRef.current.set(runId, stop)
        },
        [applyStatus],
    )

    useEffect(() => {
        if (!project) {
            runsRef.current = {}
            setRuns({})
            return
        }

        let cancelled = false
        const pollers = pollersRef.current

        const load = async () => {
            setIsLoading(true)
            try {
                const items = await getPipelineHistory(project.uuid)
                if (cancelled) {
                    return
                }

                const nextRuns: Record<string, RunRecord> = {}
                for (const item of items) {
                    if (deletedRunIdsRef.current.has(item.runId)) continue
                    nextRuns[item.runId] = summaryToRunRecord(item)
                }
                runsRef.current = nextRuns
                setRuns(nextRuns)

                for (const record of Object.values(nextRuns)) {
                    if (!isSettled(record.status)) {
                        beginPolling(record.runId)
                    }
                }
            } catch {
                // The sidebar keeps showing an empty/last-known list; it isn't the
                // place to surface a fetch error, the main panel reports run failures.
            } finally {
                if (!cancelled) {
                    setIsLoading(false)
                }
            }
        }

        void load()

        return () => {
            cancelled = true
            for (const stop of pollers.values()) {
                stop()
            }
            pollers.clear()
        }
    }, [project?.uuid, beginPolling, project])

    const getRun = useCallback((runId: string) => runsRef.current[runId], [])

    const hasActiveRun = useCallback(
        (templateUuid: string) =>
            Object.values(runsRef.current).some(
                (run) => run.templateUuid === templateUuid && !isSettled(run.status),
            ),
        [],
    )

    const startRun = useCallback(
        async (templateUuid: string, language: string): Promise<RunRecord | null> => {
            if (!project) {
                toast.error('Project is not available.')
                return null
            }

            if (!templateUuid) {
                toast.error('Select a DMP template.')
                return null
            }

            if (hasActiveRun(templateUuid)) return null

            setIsStarting(true)

            try {
                const status = await runPipeline({
                    questionnaireUuid: project.uuid,
                    templateUuid,
                    language,
                })
                const record = applyStatus(status)
                if (!isSettled(record.status)) {
                    beginPolling(record.runId)
                }
                return record
            } catch (error) {
                toast.error(error instanceof Error ? error.message : 'Pipeline execution failed.')
                return null
            } finally {
                setIsStarting(false)
            }
        },
        [project, applyStatus, beginPolling, hasActiveRun],
    )

    const cancelRun = useCallback(
        async (runId: string): Promise<void> => {
            if (cancellingRef.current.has(runId)) return
            cancellingRef.current.add(runId)
            setCancellingRunIds(new Set(cancellingRef.current))
            const originalRun = runsRef.current[runId]
            try {
                // Keep the current status/poller until the server confirms the outcome.
                // The run may finish successfully while cancellation is being requested.
                const status = await cancelPipeline(runId)
                // Do not add the run back if it has left the current project's history.
                if (!originalRun || !runsRef.current[runId]) return
                // stop() also ignores an in-flight poll response, so stale "running"
                // data cannot overwrite the cancellation response we apply below.
                pollersRef.current.get(runId)?.()
                pollersRef.current.delete(runId)
                applyStatus(status)
                if (!isSettled(status.status)) beginPolling(runId)
            } catch (error) {
                toast.error(error instanceof Error ? error.message : 'Failed to cancel pipeline.')
            } finally {
                cancellingRef.current.delete(runId)
                setCancellingRunIds(new Set(cancellingRef.current))
            }
        },
        [applyStatus, beginPolling],
    )

    const deleteRun = useCallback(async (runId: string): Promise<boolean> => {
        const run = runsRef.current[runId]
        if (!run || !isSettled(run.status) || deletingRef.current.has(runId)) return false
        deletingRef.current.add(runId)
        setDeletingRunIds(new Set(deletingRef.current))
        try {
            await deletePipeline(runId)
            deletedRunIdsRef.current.add(runId)
            pollersRef.current.get(runId)?.()
            pollersRef.current.delete(runId)
            const nextRuns = { ...runsRef.current }
            delete nextRuns[runId]
            runsRef.current = nextRuns
            setRuns(nextRuns)
            return true
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : 'Failed to delete the pipeline run.',
            )
            return false
        } finally {
            deletingRef.current.delete(runId)
            setDeletingRunIds(new Set(deletingRef.current))
        }
    }, [])

    const ensureDetailLoaded = useCallback(
        (runId: string) => {
            if (runsRef.current[runId]?.hasDetail) {
                return
            }

            void (async () => {
                try {
                    const status = await getPipelineStatus(runId)
                    applyStatus(status)
                } catch (error) {
                    if (deletedRunIdsRef.current.has(runId)) return
                    toast.error(
                        error instanceof Error
                            ? error.message
                            : 'Failed to load the generation result.',
                    )
                }
            })()
        },
        [applyStatus],
    )

    return {
        items: Object.values(runs).sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
        isLoading,
        isStarting,
        hasActiveRun,
        deletingRunIds,
        deleteRun,
        cancellingRunIds,
        cancelRun,
        getRun,
        startRun,
        ensureDetailLoaded,
        applyStatus,
    }
}
