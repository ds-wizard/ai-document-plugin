import { useCallback, useEffect, useState } from 'react'

import { getPipelineStatus, runPipeline } from '@/client'
import { SettingsData } from '@/data/settings-data'
import type { FeedbackController } from '@/hooks/useFeedback'

const POLL_INTERVAL_MS = 10_000

type PipelineProject = {
    uuid: string
} | null | undefined

export type UsePipelineResult = {
    isRunning: boolean
    /** Run id of the last completed pipeline, used when saving an edited result. */
    resultRunId: string | null
    /** Markdown produced by the last completed pipeline, or `null` before/while running. */
    resultMarkdown: string | null
    run: (templateUuid: string) => Promise<void>
}

/**
 * Owns the full pipeline lifecycle: kicking off a run, polling its status until
 * it settles, and exposing the resulting markdown. The status polling used to
 * live in a separate `PipelineStatusPoller` component wired up through nine
 * setter props; it is now an internal effect keyed on the active run id.
 */
export function usePipeline(
    project: PipelineProject,
    settings: SettingsData,
    feedback: FeedbackController,
): UsePipelineResult {
    const [activeRunId, setActiveRunId] = useState<string | null>(null)
    const [isRunning, setIsRunning] = useState(false)
    const [resultRunId, setResultRunId] = useState<string | null>(null)
    const [resultMarkdown, setResultMarkdown] = useState<string | null>(null)

    // The feedback methods are stable; depend on them individually so a changing
    // `feedback.current` never restarts the polling effect below.
    const { notifyError: notifyError, notifyInfo: notifyInfo, notifySuccess: notifySuccess, clear: clearFeedback } =
        feedback

    const run = useCallback(
        async (templateUuid: string) => {
            if (!project) {
                notifyError('Project is not available.')
                return
            }

            if (!templateUuid) {
                notifyError('Select a DMP template.')
                return
            }

            setIsRunning(true)
            clearFeedback()
            setResultRunId(null)
            setResultMarkdown(null)

            try {
                const data = await runPipeline({
                    questionnaireUuid: project.uuid,
                    templateUuid,
                    llmModel: settings.model || null,
                    llmApiKey: settings.apiKey || null,
                    llmApiUrl: settings.apiUrl || null,
                    llmMaxWorkers: settings.maxWorkers ?? null,
                })

                setActiveRunId(data.runId)
                notifyInfo(`Pipeline has been accepted for the template "${data.templateTitle}".`)
            } catch (error) {
                notifyError(error instanceof Error ? error.message : 'Pipeline execution failed.')
                setIsRunning(false)
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
        ],
    )

    useEffect(() => {
        if (!activeRunId) {
            return
        }

        let cancelled = false
        let timeoutId: ReturnType<typeof window.setTimeout> | undefined

        const sleep = (ms: number) =>
            new Promise<void>((resolve) => {
                timeoutId = window.setTimeout(() => {
                    timeoutId = undefined
                    resolve()
                }, ms)
            })

        const pollStatus = async (): Promise<boolean> => {
            try {
                const data = await getPipelineStatus(activeRunId)

                if (data.status === 'queued' || data.status === 'running') {
                    notifyInfo(
                        data.progressMessage ||
                            `Pipeline is running for the template "${data.templateTitle}".`,
                    )
                    return true
                }

                setActiveRunId(null)
                setIsRunning(false)

                if (data.status === 'succeeded') {
                    setResultRunId(data.runId)
                    setResultMarkdown(data.resultMarkdown)
                    notifySuccess(
                        `Pipeline has been completed for the template "${data.templateTitle}".`,
                    )
                    return false
                }

                notifyError(
                    data.error?.message
                        ? `Pipeline failed: ${data.error.message}`
                        : `Pipeline failed for the template "${data.templateTitle}".`,
                )
                return false
            } catch (error) {
                setActiveRunId(null)
                setIsRunning(false)
                notifyError(
                    error instanceof Error ? error.message : 'Unable to determine pipeline status.',
                )
                return false
            }
        }

        const runPolling = async () => {
            while (!cancelled) {
                const shouldContinue = await pollStatus()
                if (!shouldContinue || cancelled) {
                    break
                }
                await sleep(POLL_INTERVAL_MS)
            }
        }

        void runPolling()

        return () => {
            cancelled = true
            if (timeoutId !== undefined) {
                window.clearTimeout(timeoutId)
            }
        }
    }, [activeRunId, notifyInfo, notifySuccess, notifyError])

    return { isRunning, resultRunId, resultMarkdown, run }
}
