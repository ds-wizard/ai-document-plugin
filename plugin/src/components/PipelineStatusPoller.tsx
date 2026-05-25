import { useEffect } from 'react'

import { getPipelineStatus } from '@/client'

type PipelineStatusPollerProps = {
    activeRunId: string
    apiBaseUrl: string
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
    apiBaseUrl,
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
        const pollStatus = async () => {
            try {
                const data = await getPipelineStatus(apiBaseUrl, activeRunId)

                if (data.status === 'running') {
                    const progressDetail = data.progressMessage
                    setInfoMessage(
                        progressDetail
                            ? progressDetail
                            : `Pipeline is running for the template "${data.templateTitle}".`,
                    )
                    return
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
                    return
                }

                setSuccessMessage(null)
                setErrorMessage(
                    data.error
                        ? `Pipeline failed: ${data.error}`
                        : `Pipeline failed for the template "${data.templateTitle}".`,
                )
            } catch (error) {
                setActiveRunId(null)
                setIsRunningPipeline(false)
                setSuccessMessage(null)
                setInfoMessage(null)
                setErrorMessage(
                    error instanceof Error ? error.message : 'Unable to determine pipeline status.',
                )
            }
        }

        void pollStatus()
        const intervalId = window.setInterval(() => {
            void pollStatus()
        }, 2000)

        return () => {
            window.clearInterval(intervalId)
        }
    }, [
        activeRunId,
        apiBaseUrl,
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
