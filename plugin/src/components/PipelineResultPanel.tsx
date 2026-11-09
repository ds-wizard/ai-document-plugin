import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { Card } from '@ds-wizard/plugin-sdk/ui/Card'
import { TextareaField } from '@ds-wizard/plugin-sdk/ui/Field'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { saveEditedPipelineResult } from '@/client'
import { DownloadDropdown } from '@/components/DownloadDropdown'
import styles from '@/components/PipelineResultPanel.module.css'
import { MarkdownRenderer } from '@/markdown-utils'
import type { PipelineStatusResponse, ResultRenderMode } from '@/types'

type PipelineResultPanelProps = {
    projectUuid: string
    resultMarkdown: string | null
    resultRunId: string | null
    downloadBaseName: string
    onSaved?: (status: PipelineStatusResponse) => void
}

export function PipelineResultPanel({
    projectUuid,
    resultMarkdown,
    resultRunId,
    downloadBaseName,
    onSaved,
}: PipelineResultPanelProps) {
    const [editableResultMarkdown, setEditableResultMarkdown] = useState('')
    const [committedMarkdown, setCommittedMarkdown] = useState<string | null>(null)
    const [resultRenderMode, setResultRenderMode] = useState<ResultRenderMode>('formatted')
    const [isSavingEditedVersion, setIsSavingEditedVersion] = useState(false)

    useEffect(() => {
        setEditableResultMarkdown(resultMarkdown ?? '')
        setCommittedMarkdown(resultMarkdown)
    }, [resultMarkdown])

    const displayedResultMarkdown = resultMarkdown !== null ? editableResultMarkdown : null
    const hasResultChanges =
        resultMarkdown !== null && editableResultMarkdown !== (committedMarkdown ?? '')

    const onCopyMarkdown = async () => {
        if (!displayedResultMarkdown) {
            return
        }

        try {
            await navigator.clipboard.writeText(displayedResultMarkdown)
            toast.success('Markdown has been copied to the clipboard.')
        } catch {
            toast.error('Failed to copy markdown to the clipboard.')
        }
    }

    const onSaveEditedVersion = async () => {
        if (!resultRunId || !resultMarkdown) {
            toast.error('There is no pipeline result to save yet.')
            return
        }

        setIsSavingEditedVersion(true)
        try {
            const data = await saveEditedPipelineResult(resultRunId, editableResultMarkdown)

            const savedMarkdown = data.resultMarkdown ?? editableResultMarkdown
            setCommittedMarkdown(savedMarkdown)
            setEditableResultMarkdown(savedMarkdown)
            onSaved?.(data)
            toast.success('Edited markdown has been saved.')
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : 'Failed to save the edited version.',
            )
        } finally {
            setIsSavingEditedVersion(false)
        }
    }

    return (
        <Stack>
            <Inline align="between">
                <div role="group" aria-label="View">
                    <Inline>
                        {(
                            [
                                {
                                    mode: 'formatted' as const,
                                    label: 'Formatted',
                                    dataCy: 'dt-editor_preview-mode_project',
                                },
                                {
                                    mode: 'raw' as const,
                                    label: 'Raw',
                                    dataCy: 'dt-editor_preview-mode_km-editor',
                                },
                            ] as const
                        ).map(({ mode, label, dataCy }) => (
                            <Button
                                key={mode}
                                pressed={resultRenderMode === mode}
                                onClick={() => setResultRenderMode(mode)}
                                data-cy={dataCy}
                            >
                                {label}
                            </Button>
                        ))}
                    </Inline>
                </div>

                {displayedResultMarkdown ? (
                    <Inline align="end">
                        <Button icon="fa-copy" onClick={() => void onCopyMarkdown()}>
                            Copy markdown
                        </Button>

                        <DownloadDropdown
                            markdown={displayedResultMarkdown}
                            runId={resultRunId}
                            baseName={downloadBaseName}
                        />
                    </Inline>
                ) : null}
            </Inline>

            <Card className={styles.body}>
                {!resultMarkdown ? (
                    <Muted>
                        The generated markdown will appear here after a successful pipeline run.
                    </Muted>
                ) : resultRenderMode === 'raw' ? (
                    <Stack>
                        <Inline align="end">
                            <Button
                                icon="fa-floppy-disk"
                                loading={isSavingEditedVersion}
                                disabledReason={
                                    hasResultChanges
                                        ? undefined
                                        : {
                                              id: `ai-doc-save-reason-${resultRunId ?? 'result'}`,
                                              reason: 'There are no changes to save.',
                                          }
                                }
                                onClick={() => void onSaveEditedVersion()}
                            >
                                {isSavingEditedVersion ? 'Saving...' : 'Save'}
                            </Button>
                        </Inline>

                        <TextareaField
                            label="Markdown"
                            hiddenLabel
                            value={editableResultMarkdown}
                            onChange={setEditableResultMarkdown}
                            className={styles.rawField}
                        />
                    </Stack>
                ) : (
                    <MarkdownRenderer
                        markdown={displayedResultMarkdown || ''}
                        projectUuid={projectUuid}
                    />
                )}
            </Card>
        </Stack>
    )
}
