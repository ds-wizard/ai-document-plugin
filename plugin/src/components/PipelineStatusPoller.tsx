import { useEffect } from 'react'

import { getPipelineStatus } from '@/client'

type PipelineStatusPollerProps = {
    activeRunId: string
    setActiveRunId: (value: string | null) => void
    setIsRunningPipeline: (value: boolean) => void
    setInfoMessage: (value: string | null) => void
    setSuccessMessage: (value: string | null) => void
    setErrorMessage: (value: string | null) => void
    setResultRunId: (value: string | null) => void
    setResultMarkdown: (value: string | null) => void
    setEditableResultMarkdown: (value: string) => void
}

export function PipelineStatusPoller({
    activeRunId,
    setActiveRunId,
    setIsRunningPipeline,
    setInfoMessage,
    setSuccessMessage,
    setErrorMessage,
    setResultRunId,
    setResultMarkdown,
    setEditableResultMarkdown,
}: PipelineStatusPollerProps) {
    useEffect(() => {
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
                    const progressDetail = data.progressMessage
                    setInfoMessage(
                        progressDetail
                            ? progressDetail
                            : `Pipeline is running for the template "${data.templateTitle}".`,
                    )
                    return true
                }

                setActiveRunId(null)
                setIsRunningPipeline(false)
                setInfoMessage(null)

                if (data.status === 'succeeded') {
                    setResultRunId(data.runId)
                    setResultMarkdown(data.resultMarkdown)
                    setEditableResultMarkdown(data.resultMarkdown || '')
                    setSuccessMessage(
                        `Pipeline has been completed for the template "${data.templateTitle}".`,
                    )
                    setErrorMessage(null)
                    return false
                }

                setSuccessMessage(null)
                setErrorMessage(
                    data.error?.message
                        ? `Pipeline failed: ${data.error.message}`
                        : `Pipeline failed for the template "${data.templateTitle}".`,
                )
                return false
            } catch (error) {
                setActiveRunId(null)
                setIsRunningPipeline(false)
                setSuccessMessage(null)
                setInfoMessage(null)
                setErrorMessage(
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
                await sleep(10_000)
            }
        }

        void runPolling()

        return () => {
            cancelled = true
            if (timeoutId !== undefined) {
                window.clearTimeout(timeoutId)
            }
        }
    }, [
        activeRunId,
        setActiveRunId,
        setEditableResultMarkdown,
        setErrorMessage,
        setInfoMessage,
        setIsRunningPipeline,
        setResultMarkdown,
        setResultRunId,
        setSuccessMessage,
    ])

    return null
}
