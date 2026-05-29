import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { getApiUrlAndToken } from '@ds-wizard/plugin-sdk/requests'
import { useCallback, useEffect, useState } from 'react'

import { runPipeline } from '@/client'
import { Alert } from '@/components/Alert'
import { DmpTemplateSection } from '@/components/DmpTemplateSection'
import { ExportView } from '@/components/ExportView'
import styles from '@/components/ProjectTab.module.css'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import {
    getAiExportIdFromUrl,
    navigateBackFromExport,
    pushAiExportIdToUrl,
} from '@/utils/export-url'
import { getLastExportRunId, setLastExportRunId } from '@/utils/last-export-cookie'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const [exportRunId, setExportRunId] = useState<string | null>(() => getAiExportIdFromUrl())
    const [mainErrorMessage, setMainErrorMessage] = useState<string | null>(null)

    const projectUuid = project?.uuid
    const lastExportRunId = projectUuid ? getLastExportRunId(projectUuid) : null

    useEffect(() => {
        const syncExportRunIdFromUrl = () => {
            setExportRunId(getAiExportIdFromUrl())
        }

        window.addEventListener('popstate', syncExportRunIdFromUrl)
        return () => window.removeEventListener('popstate', syncExportRunIdFromUrl)
    }, [])

    const openExportView = useCallback((runId: string) => {
        pushAiExportIdToUrl(runId)
        setExportRunId(runId)
    }, [])

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

                setLastExportRunId(project.uuid, data.runId)
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
                {!exportRunId ? (
                    <>
                        <div>
                            <h2 className={styles.title}>AI DMP Export</h2>
                            <p className={styles.lead}>
                                Convert your Questionnaire to a DMP. Select a DMP Template to
                                continue.
                            </p>
                        </div>

                        {!project ? (
                            <Alert variant="warning">
                                The project is not loaded; the pipeline cannot be started yet.
                            </Alert>
                        ) : null}

                        <DmpTemplateSection
                            projectAvailable={Boolean(project)}
                            hasLastExport={Boolean(lastExportRunId)}
                            onRunPipeline={(templateUuid) => void handleRunPipeline(templateUuid)}
                            onShowLastExport={handleShowLastExport}
                        />

                        <Alert variant="error">{mainErrorMessage}</Alert>
                    </>
                ) : exportRunId && projectUuid ? (
                    <ExportView
                        key={exportRunId}
                        runId={exportRunId}
                        projectUuid={projectUuid}
                        onBack={navigateBackFromExport}
                    />
                ) : null}
            </div>
        </div>
    )
}
