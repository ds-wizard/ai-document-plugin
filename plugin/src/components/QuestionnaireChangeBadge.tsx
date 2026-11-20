import { Badge } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Spinner } from '@ds-wizard/plugin-sdk/ui/Icon'

import type { RunRecord } from '@/hooks/useGenerationHistory'
import {
    getQuestionnaireChange,
    type LatestQuestionnaireEvent,
} from '@/hooks/useLatestQuestionnaireEvent'

type QuestionnaireChangeBadgeProps = {
    run: Pick<RunRecord, 'status' | 'sourceEventUuid'>
    latestEvent: LatestQuestionnaireEvent
}

/** A small badge saying whether the questionnaire answers may have changed since the document was generated. */
export function QuestionnaireChangeBadge({ run, latestEvent }: QuestionnaireChangeBadgeProps) {
    if (run.status !== 'succeeded') return null

    if (latestEvent.status === 'loading') {
        return <Spinner label="Checking the questionnaire for changes" />
    }

    const change = getQuestionnaireChange(run, latestEvent)

    if (change === 'changed') {
        return (
            <Badge
                tone="warning"
                icon="fa-triangle-exclamation"
                description="Some answers may have been edited since this document was generated."
            >
                Questionnaire changed after the DMP was generated
            </Badge>
        )
    }

    // Unchanged, or not verifiable (older run, DSW unreachable): nothing to show.
    return null
}
