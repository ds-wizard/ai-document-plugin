import { useEffect, useState } from 'react'

import { getLatestQuestionnaireEventUuid } from '@/client'

export type LatestQuestionnaireEvent =
    { status: 'loading' } | { status: 'failed' } | { status: 'ready'; eventUuid: string }

/**
 * The newest DSW event of the questionnaire, read once when the project tab opens. Runs are compared against
 * it, so opening several runs costs a single request to DSW.
 */
export function useLatestQuestionnaireEvent(
    questionnaireUuid: string | undefined,
): LatestQuestionnaireEvent {
    const [latest, setLatest] = useState<LatestQuestionnaireEvent>({ status: 'loading' })

    useEffect(() => {
        setLatest({ status: 'loading' })
        if (!questionnaireUuid) return

        let cancelled = false
        void getLatestQuestionnaireEventUuid(questionnaireUuid)
            .then((eventUuid) => {
                if (!cancelled) setLatest({ status: 'ready', eventUuid })
            })
            .catch(() => {
                if (!cancelled) setLatest({ status: 'failed' })
            })

        return () => {
            cancelled = true
        }
    }, [questionnaireUuid])

    return latest
}

/**
 * Whether the answers changed since the run read them. False when that cannot be told: the latest event is not
 * loaded or could not be read, or the run is older and has no event of its own.
 *
 * The check is conservative: phase and label edits, and re-saving the same value, also count as a change.
 */
export function isQuestionnaireChanged(
    sourceEventUuid: string | null,
    latest: LatestQuestionnaireEvent,
): boolean {
    return (
        latest.status === 'ready' &&
        sourceEventUuid !== null &&
        latest.eventUuid.toLowerCase() !== sourceEventUuid.toLowerCase()
    )
}
