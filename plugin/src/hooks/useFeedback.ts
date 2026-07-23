import { useCallback, useMemo, useState } from 'react'

export type FeedbackKind = 'error' | 'info' | 'success'

export type Feedback = {
    kind: FeedbackKind
    text: string
}

export type FeedbackController = {
    /** The single feedback message currently shown, or `null` when there is none. */
    current: Feedback | null
    notifyError: (text: string) => void
    notifyInfo: (text: string) => void
    notifySuccess: (text: string) => void
    clear: () => void
}

/**
 * Holds a single user-facing message. Error, info, and success are mutually
 * exclusive: showing one replaces whatever was there before, which removes the
 * manual `setErrorMessage(null)` dance that surrounded every notification.
 */
export function useFeedback(): FeedbackController {
    const [current, setCurrent] = useState<Feedback | null>(null)

    const notifyError = useCallback((text: string) => setCurrent({ kind: 'error', text }), [])
    const notifyInfo = useCallback((text: string) => setCurrent({ kind: 'info', text }), [])
    const notifySuccess = useCallback((text: string) => setCurrent({ kind: 'success', text }), [])
    const clear = useCallback(() => setCurrent(null), [])

    return useMemo(
        () => ({ current, notifyError, notifyInfo, notifySuccess, clear }),
        [current, notifyError, notifyInfo, notifySuccess, clear],
    )
}
