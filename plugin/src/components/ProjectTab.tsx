import { ProjectTabComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { useCallback, useEffect, useRef, useState } from 'react'
import { toast, Toaster } from 'sonner'

import { getAvailableLanguages, getQuestionnaireLanguage } from '@/client'
import { HistorySidebar } from '@/components/HistorySidebar'
import styles from '@/components/ProjectTab.module.css'
import { ProjectTemplatePanel } from '@/components/ProjectTemplatePanel'
import { RunDetailPanel } from '@/components/RunDetailPanel'
import { buildLanguageOptions, getLanguageOption, type LanguageOption } from '@/data/languages'
import { SettingsData } from '@/data/settings-data'
import { UserSettingsData } from '@/data/user-settings-data'
import { useGenerationHistory } from '@/hooks/useGenerationHistory'
import { useTemplates } from '@/hooks/useTemplates'

const DEFAULT_LANGUAGE = 'en'

export default function ProjectTab({
    settings,
    userSettings: _userSettings,
    project,
}: ProjectTabComponentProps<SettingsData, UserSettingsData>) {
    const templates = useTemplates({
        reloadKey: settings.serviceUrl,
        onLoadError: toast.error,
    })
    const history = useGenerationHistory(project)
    const projectUuid = project?.uuid

    const [selectedUuid, setSelectedUuid] = useState('')
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
    const [language, setLanguage] = useState('')
    const [languageOptions, setLanguageOptions] = useState<LanguageOption[]>([])
    const [languagesLoading, setLanguagesLoading] = useState(true)
    const userSelectedLanguage = useRef(false)

    const handleLanguageChange = useCallback((nextLanguage: string) => {
        userSelectedLanguage.current = true
        setLanguage(nextLanguage)
    }, [])

    useEffect(() => {
        let cancelled = false
        setLanguagesLoading(true)
        setLanguageOptions([])

        void getAvailableLanguages()
            .then((definitions) => {
                if (cancelled) return
                const options = buildLanguageOptions(definitions)
                if (options.length === 0) {
                    throw new Error('No languages are available from the API.')
                }
                setLanguageOptions(options)
            })
            .catch((error: unknown) => {
                if (!cancelled) {
                    toast.error(
                        error instanceof Error
                            ? error.message
                            : 'Failed to load available languages.',
                    )
                }
            })
            .finally(() => {
                if (!cancelled) setLanguagesLoading(false)
            })

        return () => {
            cancelled = true
        }
    }, [settings.serviceUrl])

    useEffect(() => {
        userSelectedLanguage.current = false
        setLanguage('')

        if (languageOptions.length === 0) return

        const fallbackLanguage =
            getLanguageOption(languageOptions, DEFAULT_LANGUAGE)?.code ?? languageOptions[0].code

        if (!projectUuid) {
            setLanguage(fallbackLanguage)
            return
        }

        let cancelled = false
        void getQuestionnaireLanguage(projectUuid)
            .then((questionnaireLanguage) => {
                if (!cancelled && !userSelectedLanguage.current) {
                    setLanguage(
                        getLanguageOption(languageOptions, questionnaireLanguage ?? '')?.code ??
                            fallbackLanguage,
                    )
                }
            })
            .catch(() => {
                if (!cancelled && !userSelectedLanguage.current) {
                    setLanguage(fallbackLanguage)
                }
            })

        return () => {
            cancelled = true
        }
    }, [projectUuid, languageOptions])

    if (!project) {
        return (
            <Stack>
                <Alert tone="warning">
                    The project is not loaded; the pipeline cannot be started yet.
                </Alert>
                <Toaster richColors closeButton />
            </Stack>
        )
    }

    const handleRunPipeline = async () => {
        const started = await history.startRun(selectedUuid, language)
        if (started) {
            setSelectedRunId(started.runId)
        }
    }

    // Why the pipeline cannot be run yet; starting it shows on the button as loading instead.
    const runUnavailableReason =
        templates.isLoading || languagesLoading
            ? 'Templates and languages are still loading.'
            : languageOptions.length === 0
              ? 'No languages are available.'
              : !selectedUuid
                ? 'Select a template first.'
                : !getLanguageOption(languageOptions, language)
                  ? 'Select a language first.'
                  : null

    return (
        // Edge to edge: the history sidebar runs along the tab's edge, the main panel pads itself.
        <div className={styles.layout}>
            <HistorySidebar
                history={history}
                selectedRunId={selectedRunId}
                onSelectNew={() => setSelectedRunId(null)}
                onSelectRun={setSelectedRunId}
            />

            <div className={styles.main}>
                <div className={styles.content}>
                    {selectedRunId ? (
                        <RunDetailPanel
                            runId={selectedRunId}
                            history={history}
                            projectUuid={project.uuid}
                        />
                    ) : (
                        <Stack loose>
                            <ProjectTemplatePanel
                                templates={templates}
                                selectedUuid={selectedUuid}
                                onSelectedUuidChange={setSelectedUuid}
                                disabled={history.isStarting}
                                language={language}
                                languageOptions={languageOptions}
                                languagesLoading={languagesLoading}
                                onLanguageChange={handleLanguageChange}
                            />

                            <Inline>
                                <Button
                                    variant="primary"
                                    icon="fa-play"
                                    loading={history.isStarting}
                                    disabledReason={
                                        runUnavailableReason && !history.isStarting
                                            ? {
                                                  id: 'ai-doc-run-pipeline-reason',
                                                  reason: runUnavailableReason,
                                              }
                                            : undefined
                                    }
                                    onClick={() => void handleRunPipeline()}
                                >
                                    {history.isStarting ? 'Starting pipeline...' : 'Run pipeline'}
                                </Button>
                            </Inline>
                        </Stack>
                    )}
                </div>
            </div>
            <Toaster richColors closeButton />
        </div>
    )
}
