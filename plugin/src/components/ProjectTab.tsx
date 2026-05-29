import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { useCallback, useEffect, useState } from 'react'

import { runPipeline } from '@/client'
import { DmpTemplateSection } from '@/components/DmpTemplateSection'
import { ExportView } from '@/components/ExportView'
import styles from '@/components/ProjectTab.module.css'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import type { PipelineStatusResponse } from '@/types'
import { getLastExportRunId, setLastExportRunId } from '@/utils/last-export-cookie'

type ProjectTabView = 'main' | 'export'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const [view, setView] = useState<ProjectTabView>('main')
    const [exportRunId, setExportRunId] = useState<string | null>(null)
    const [lastExportRunId, setLastExportRunIdState] = useState<string | null>(null)
    const [mainErrorMessage, setMainErrorMessage] = useState<string | null>(null)

    const projectUuid = project?.uuid

    useEffect(() => {
        if (!projectUuid) {
            setLastExportRunIdState(null)
            return
        }

        setLastExportRunIdState(getLastExportRunId(projectUuid))
    }, [projectUuid])

    const openExportView = useCallback((runId: string) => {
        setExportRunId(runId)
        setView('export')
    }, [])

    const handlePipelineSucceeded = useCallback(
        (data: PipelineStatusResponse) => {
            if (projectUuid) {
                setLastExportRunId(projectUuid, data.runId)
                setLastExportRunIdState(data.runId)
            }
        },
        [projectUuid],
    )

    const handleRunPipeline = useCallback(
        async (templateUuid: string) => {
            if (!project) {
                setMainErrorMessage('Project is not available.')
                return
            }

            setMainErrorMessage(null)

            try {
                const { apiUrl, token } = getApiUrlAndToken()
                if (!token) {
                    throw new Error("Failed to retrieve the current user's authentication token.")
                }

                const data = await runPipeline({
                    questionnaireUuid: project.uuid,
                    templateUuid,
                    token,
                    apiUrl,
                    llmModel: settings.model || null,
                    llmApiKey: settings.apiKey || null,
                    llmApiUrl: settings.apiUrl || null,
                    llmMaxWorkers: settings.maxWorkers ?? null,
                })

                if (projectUuid) {
                    setLastExportRunId(projectUuid, data.runId)
                    setLastExportRunIdState(data.runId)
                }

                openExportView(data.runId)
            } catch (error) {
                const message =
                    error instanceof Error ? error.message : 'Pipeline execution failed.'
                setMainErrorMessage(message)
            }
        },
        [
            openExportView,
            project,
            projectUuid,
            settings.apiKey,
            settings.apiUrl,
            settings.maxWorkers,
            settings.model,
        ],
    )

    const handleShowLastExport = useCallback(() => {
        if (!lastExportRunId) {
            return
        }

        openExportView(lastExportRunId)
    }, [lastExportRunId, openExportView])

    return (
        <div className="Projects__Detail__Content Projects__Detail__Content--Metrics">
            <div className={`questionnaire__summary-report container ${styles.root}`}>
                {view === 'main' ? (
                    <>
                        <div>
                            <h2 className={styles.title}>AI DMP Export</h2>
                            <p className={styles.lead}>
                                Convert your Questionnaire to a DMP. Select a DMP Template to
                                continue.
                            </p>
                        </div>

                        {!project ? (
                            <div className={`${styles.alert} ${styles.warningAlert}`}>
                                The project is not loaded; the pipeline cannot be started yet.
                            </div>
                        ) : null}

                        <DmpTemplateSection
                            projectAvailable={Boolean(project)}
                            hasLastExport={Boolean(lastExportRunId)}
                            onRunPipeline={(templateUuid) => void handleRunPipeline(templateUuid)}
                            onShowLastExport={handleShowLastExport}
                        />

                        {mainErrorMessage ? (
                            <div className={`${styles.alert} ${styles.errorAlert}`}>
                                {mainErrorMessage}
                            </div>
                        ) : null}
                    </>
                ) : exportRunId ? (
                    <ExportView
                        key={exportRunId}
                        runId={exportRunId}
                        onBack={() => setView('main')}
                        onPipelineSucceeded={handlePipelineSucceeded}
                    />
                ) : null}
            </div>
        </div>
    )
}
