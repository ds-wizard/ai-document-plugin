import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { useCallback, useState } from 'react'
import { toast,Toaster } from 'sonner'

import { FeedbackAlert } from '@/components/FeedbackAlert'
import { HistorySidebar } from '@/components/HistorySidebar'
import styles from '@/components/ProjectTab.module.css'
import { ProjectTemplatePanel } from '@/components/ProjectTemplatePanel'
import { RunDetailPanel } from '@/components/RunDetailPanel'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import { useGenerationHistory } from '@/hooks/useGenerationHistory'
import { useTemplates } from '@/hooks/useTemplates'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const templates = useTemplates({
        reloadKey: settings.serviceUrl,
        onLoadError: toast.error,
    })
    const history = useGenerationHistory(project, settings)

    const [selectedUuid, setSelectedUuid] = useState('')
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

    const handleSelectedUuidChange = useCallback((uuid: string) => {
        setSelectedUuid(uuid)
    }, [])

    if (!project) {
        return (
            <div>
                <Toaster richColors closeButton />
                <div className={styles.root}>
                    <div>
                        <h2 className="ai-doc-title">AI Document Generation</h2>
                    </div>

                    <FeedbackAlert kind="warning">
                        The project is not loaded; the pipeline cannot be started yet.
                    </FeedbackAlert>
                </div>
            </div>
        )
    }

    const handleRunPipeline = async () => {
        const started = await history.startRun(selectedUuid)
        if (started) {
            setSelectedRunId(started.runId)
        }
    }

    return (
        <div className="Projects__Detail__Content Projects__Detail__Content--Metrics">
            <Toaster richColors closeButton />
            <div className={`questionnaire__summary-report ${styles.layout}`}>
                <HistorySidebar
                    history={history}
                    selectedRunId={selectedRunId}
                    onSelectNew={() => setSelectedRunId(null)}
                    onSelectRun={setSelectedRunId}
                />

                <div className={styles.main}>
                    {selectedRunId ? (
                        <RunDetailPanel runId={selectedRunId} history={history} />
                    ) : (
                        <div className={styles.root}>
                            <div>
                                <h2 className="ai-doc-title">AI Document Generation</h2>
                            </div>

                            <ProjectTemplatePanel
                                templates={templates}
                                disabled={history.isStarting}
                                onSelectedUuidChange={handleSelectedUuidChange}
                            />

                            <button
                                type="button"
                                onClick={() => void handleRunPipeline()}
                                disabled={
                                    templates.isLoading || history.isStarting || !selectedUuid
                                }
                                className={`btn btn-primary btn-wide ${styles.runButton}`}
                            >
                                {history.isStarting ? 'Starting pipeline...' : 'Run pipeline'}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
