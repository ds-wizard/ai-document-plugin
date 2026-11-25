import { Badge } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Spinner } from '@ds-wizard/plugin-sdk/ui/Icon'
import { useState } from 'react'

import { QuestionnaireChangesModal } from '@/components/QuestionnaireChangesModal'
import type { RunRecord } from '@/hooks/useGenerationHistory'
import {
    isQuestionnaireChanged,
    type LatestQuestionnaireEvent,
} from '@/hooks/useLatestQuestionnaireEvent'

type QuestionnaireChangeBadgeProps = {
    run: Pick<RunRecord, 'runId' | 'status' | 'sourceEventUuid'>
    latestEvent: LatestQuestionnaireEvent
}

/**
 * A small badge saying whether the questionnaire answers may have changed since the document was generated.
 * Clicking it lists what changed.
 */
export function QuestionnaireChangeBadge({ run, latestEvent }: QuestionnaireChangeBadgeProps) {
    const [isOpen, setIsOpen] = useState(false)

    if (run.status !== 'succeeded') return null

    if (latestEvent.status === 'loading') {
        return <Spinner label="Checking the questionnaire for changes" />
    }

    // Unchanged, or not verifiable (older run, DSW unreachable): nothing to show.
    if (!isQuestionnaireChanged(run.sourceEventUuid, latestEvent)) return null

    return (
        <>
            <Badge
                tone="warning"
                icon="fa-triangle-exclamation"
                description="Some answers may have been edited since this document was generated. Click to see what changed."
                onClick={() => setIsOpen(true)}
            >
                Questionnaire changed after the DMP was generated
            </Badge>
            {isOpen && (
                <QuestionnaireChangesModal runId={run.runId} onClose={() => setIsOpen(false)} />
            )}
        </>
    )
}
