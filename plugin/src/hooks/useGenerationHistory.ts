import { useCallback, useEffect, useRef, useState } from 'react'

import { getPipelineHistory, getPipelineStatus, runPipeline } from '@/client'
import { SettingsData } from '@/data/settings-data'
import type { FeedbackController } from '@/hooks/useFeedback'
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
    status: RunStatusValue
    templateTitle: string
    error: PipelineErrorResponse | null
    progressMessage: string | null
    createdAt: string
    updatedAt: string
    resultMarkdown: string | null
    /** false = came only from the summary list, never polled/backfilled with full detail. */
    hasDetail: boolean
}

export type UseGenerationHistoryResult = {
    items: RunRecord[]
    isLoading: boolean
    isStarting: boolean
    // returns a reference to a generation run.
    // This helps with handling live updates from the pollers without need to do subscribe logic
    getRun: (runId: string) => RunRecord | undefined
    startRun: (templateUuid: string) => Promise<RunRecord | null>
    ensureDetailLoaded: (runId: string) => void
    applyStatus: (status: PipelineStatusResponse) => RunRecord
}

const summaryToRunRecord = (item: PipelineSummaryItem): RunRecord => ({
    runId: item.runId,
    status: item.status,
    templateTitle: item.templateTitle,
    error: item.error,
    progressMessage: item.progressMessage,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
    resultMarkdown: null,
    hasDetail: false,
})

const isSettled = (status: RunStatusValue): boolean => status === 'succeeded' || status === 'failed'

/**
 * Owns every run belonging to the project: the initial history load, starting new
 * runs, and polling in-progress ones. Exactly one poller exists per in-progress run,
 * started once (at load or right after `startRun`) and stopped once it settles.
 * The sidebar and the detail view both read the same `RunRecord`s from here, so they
 * can never disagree with each other.
 */
export function useGenerationHistory(
    project: PipelineProject,
    settings: SettingsData,
    feedback: FeedbackController,
): UseGenerationHistoryResult {
    const [runs, setRuns] = useState<Record<string, RunRecord>>({})
    const [isLoading, setIsLoading] = useState(false)
    const [isStarting, setIsStarting] = useState(false)

    // Mirrors `runs` synchronously so callbacks (applyStatus, getRun, startRun) can
    // read/merge the latest state without waiting on React's async setState.
    const runsRef = useRef<Record<string, RunRecord>>({})
    const pollersRef = useRef<Map<string, () => void>>(new Map())

    const { notifyError, notifyInfo, clear: clearFeedback } = feedback

    const setRunRecord = useCallback((record: RunRecord) => {
        runsRef.current = { ...runsRef.current, [record.runId]: record }
        setRuns(runsRef.current)
    }, [])

    const applyStatus = useCallback(
        (status: PipelineStatusResponse): RunRecord => {
            const existing = runsRef.current[status.runId]
            const record: RunRecord = {
                runId: status.runId,
                status: status.status,
                templateTitle: status.templateTitle,
                error: status.error,
                // `PipelineStatusResponse` has no `createdAt`; keep whatever we already knew.
                createdAt: existing?.createdAt ?? status.updatedAt,
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

        const load = async () => {
            setIsLoading(true)
            try {
                const items = await getPipelineHistory(project.uuid)
                if (cancelled) {
                    return
                }

                const nextRuns: Record<string, RunRecord> = {}
                for (const item of items) {
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
            for (const stop of pollersRef.current.values()) {
                stop()
            }
            pollersRef.current.clear()
        }
    }, [project?.uuid, beginPolling])

    const getRun = useCallback((runId: string) => runsRef.current[runId], [])

    const startRun = useCallback(
        async (templateUuid: string): Promise<RunRecord | null> => {
            if (!project) {
                notifyError('Project is not available.')
                return null
            }

            if (!templateUuid) {
                notifyError('Select a DMP template.')
                return null
            }

            setIsStarting(true)
            clearFeedback()

            try {
                const status = await runPipeline({
                    questionnaireUuid: project.uuid,
                    templateUuid,
                    llmModel: settings.model || null,
                    llmApiKey: settings.apiKey || null,
                    llmApiUrl: settings.apiUrl || null,
                    llmMaxWorkers: settings.maxWorkers ?? null,
                })

                notifyInfo(`Pipeline has been accepted for the template "${status.templateTitle}".`)
                const record = applyStatus(status)
                if (!isSettled(record.status)) {
                    beginPolling(record.runId)
                }
                return record
            } catch (error) {
                notifyError(error instanceof Error ? error.message : 'Pipeline execution failed.')
                return null
            } finally {
                setIsStarting(false)
            }
        },
        [
            project,
            settings.model,
            settings.apiKey,
            settings.apiUrl,
            settings.maxWorkers,
            notifyError,
            notifyInfo,
            clearFeedback,
            applyStatus,
            beginPolling,
        ],
    )

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
                    notifyError(
                        error instanceof Error
                            ? error.message
                            : 'Failed to load the generation result.',
                    )
                }
            })()
        },
        [applyStatus, notifyError],
    )

    return {
        items: Object.values(runs).sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
        isLoading,
        isStarting,
        getRun,
        startRun,
        ensureDetailLoaded,
        applyStatus,
    }
}
