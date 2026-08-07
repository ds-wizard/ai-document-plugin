import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { useCallback, useState } from 'react'

import { FeedbackAlert } from '@/components/FeedbackAlert'
import { HistorySidebar } from '@/components/HistorySidebar'
import styles from '@/components/ProjectTab.module.css'
import { ProjectTemplatePanel } from '@/components/ProjectTemplatePanel'
import { RunDetailPanel } from '@/components/RunDetailPanel'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import { useFeedback } from '@/hooks/useFeedback'
import { useGenerationHistory } from '@/hooks/useGenerationHistory'
import { useTemplates } from '@/hooks/useTemplates'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const feedback = useFeedback()
    const templates = useTemplates({
        reloadKey: settings.serviceUrl,
        onReload: feedback.clear,
        onLoadError: feedback.notifyError,
    })
    const history = useGenerationHistory(project, settings, feedback)

    const [selectedUuid, setSelectedUuid] = useState('')
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

    const handleSelectedUuidChange = useCallback((uuid: string) => {
        setSelectedUuid(uuid)
    }, [])

    if (!project) {
        return (
            <div>
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
            <div className={`questionnaire__summary-report ${styles.layout}`}>
                <HistorySidebar
                    history={history}
                    selectedRunId={selectedRunId}
                    onSelectNew={() => setSelectedRunId(null)}
                    onSelectRun={setSelectedRunId}
                />

                <div className={styles.main}>
                    {selectedRunId ? (
                        <RunDetailPanel runId={selectedRunId} history={history} feedback={feedback} />
                    ) : (
                        <div className={styles.root}>
                            <div>
                                <h2 className="ai-doc-title">AI Document Generation</h2>
                                <p className={styles.lead}>
                                    Select a DMP template from the database and run the pipeline on
                                    the current project.
                                </p>
                            </div>

                            <ProjectTemplatePanel
                                templates={templates}
                                feedback={feedback}
                                disabled={history.isStarting}
                                onSelectedUuidChange={handleSelectedUuidChange}
                            />

                            <button
                                type="button"
                                onClick={() => void handleRunPipeline()}
                                disabled={templates.isLoading || history.isStarting || !selectedUuid}
                                className={`btn btn-primary btn-wide ${styles.runButton}`}
                            >
                                {history.isStarting ? 'Starting pipeline...' : 'Run pipeline'}
                            </button>

                            {feedback.current ? (
                                <FeedbackAlert kind={feedback.current.kind}>
                                    {feedback.current.text}
                                </FeedbackAlert>
                            ) : null}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
