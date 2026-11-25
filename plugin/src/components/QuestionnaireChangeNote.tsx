import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { Inline } from '@ds-wizard/plugin-sdk/ui/Layout'
import { useState } from 'react'

import styles from '@/components/QuestionnaireChangeNote.module.css'
import { QuestionnaireChangesModal } from '@/components/QuestionnaireChangesModal'
import type { RunRecord } from '@/hooks/useGenerationHistory'
import {
    isQuestionnaireChanged,
    type LatestQuestionnaireEvent,
} from '@/hooks/useLatestQuestionnaireEvent'

type QuestionnaireChangeNoteProps = {
    run: Pick<RunRecord, 'runId' | 'status' | 'sourceEventUuid'>
    latestEvent: LatestQuestionnaireEvent
}

/**
 * A note, shown when the questionnaire answers may have changed since the document was generated, that lists
 * what changed when clicked.
 */
export function QuestionnaireChangeNote({ run, latestEvent }: QuestionnaireChangeNoteProps) {
    const [isOpen, setIsOpen] = useState(false)

    if (run.status !== 'succeeded') return null

    // Still checking, unchanged, or not verifiable (older run, DSW unreachable): nothing to show.
    if (!isQuestionnaireChanged(run.sourceEventUuid, latestEvent)) return null

    return (
        <>
            <Alert tone="warning" className={styles.note}>
                <Inline align="between">
                    <span>DMP is outdated</span>
                    <Button size="small" variant="secondary" onClick={() => setIsOpen(true)}>
                        Show changes
                    </Button>
                </Inline>
            </Alert>
            {isOpen && (
                <QuestionnaireChangesModal runId={run.runId} onClose={() => setIsOpen(false)} />
            )}
        </>
    )
}
