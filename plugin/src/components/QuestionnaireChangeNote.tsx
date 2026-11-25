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
            <button type="button" className={styles.note} onClick={() => setIsOpen(true)}>
                <i className="fas fa-triangle-exclamation" aria-hidden="true" />
                <span className={styles.text}>Changes since DMP was created</span>
                <span className={styles.action}>
                    Show changes
                    <i className="fas fa-chevron-right" aria-hidden="true" />
                </span>
            </button>
            {isOpen && (
                <QuestionnaireChangesModal runId={run.runId} onClose={() => setIsOpen(false)} />
            )}
        </>
    )
}
