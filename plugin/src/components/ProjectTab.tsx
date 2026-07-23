import { useCallback, useState } from 'react'

import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'

import { FeedbackAlert } from '@/components/FeedbackAlert'
import { PipelineResultPanel } from '@/components/PipelineResultPanel'
import { ProjectTemplatePanel } from '@/components/ProjectTemplatePanel'
import styles from '@/components/ProjectTab.module.css'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import { useFeedback } from '@/hooks/useFeedback'
import { usePipeline } from '@/hooks/usePipeline'
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
    const pipeline = usePipeline(project, settings, feedback)

    const [selectedUuid, setSelectedUuid] = useState('')

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

    const handleRunPipeline = () => {
        void pipeline.run(selectedUuid)
    }

    return (
        <div className="Projects__Detail__Content Projects__Detail__Content--Metrics">
            <div className={`questionnaire__summary-report container ${styles.root}`}>
                <div>
                    <h2 className="ai-doc-title">AI Document Generation</h2>
                    <p className={styles.lead}>
                        Select a DMP template from the database and run the pipeline on the current
                        project.
                    </p>
                </div>

                <ProjectTemplatePanel
                    templates={templates}
                    feedback={feedback}
                    disabled={pipeline.isRunning}
                    onSelectedUuidChange={handleSelectedUuidChange}
                />

                <button
                    type="button"
                    onClick={handleRunPipeline}
                    disabled={templates.isLoading || pipeline.isRunning || !selectedUuid}
                    className={`btn btn-primary btn-wide ${styles.runButton}`}
                >
                    {pipeline.isRunning ? 'Running pipeline...' : 'Run pipeline'}
                </button>

                {feedback.current ? (
                    <FeedbackAlert kind={feedback.current.kind}>
                        {feedback.current.text}
                    </FeedbackAlert>
                ) : null}

                <PipelineResultPanel
                    resultMarkdown={pipeline.resultMarkdown}
                    resultRunId={pipeline.resultRunId}
                    feedback={feedback}
                    downloadBaseName={selectedUuid}
                />
            </div>
        </div>
    )
}
