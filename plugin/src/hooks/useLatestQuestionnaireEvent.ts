import { useEffect, useState } from 'react'

import { getLatestQuestionnaireEventUuid } from '@/client'
import type { RunRecord } from '@/hooks/useGenerationHistory'

export type LatestQuestionnaireEvent =
    | { status: 'loading' }
    | { status: 'failed' }
    | { status: 'ready'; eventUuid: string }

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
 * Whether the answers changed since the run read them: `changed`, `unknown` when that cannot be told (older
 * run, or DSW could not be asked), or `null` when there is nothing to show (unchanged, or the run has not
 * succeeded). Throws when called while the latest event is still loading, so callers must wait for it.
 *
 * The check is conservative: phase and label edits, and re-saving the same value, also count as a change.
 */
export function getQuestionnaireChange(
    run: Pick<RunRecord, 'status' | 'sourceEventUuid'>,
    latest: LatestQuestionnaireEvent,
): 'changed' | 'unknown' | null {
    if (latest.status === 'loading') {
        throw new Error('The latest questionnaire event is not loaded yet.')
    }
    if (run.status !== 'succeeded') return null
    if (latest.status === 'failed' || !run.sourceEventUuid) return 'unknown'
    return latest.eventUuid.toLowerCase() === run.sourceEventUuid.toLowerCase() ? null : 'changed'
}
