import { useCallback, useEffect, useState } from 'react'

import { getTemplate } from '@/client'
import type { TemplateDetail } from '@/types'

export type UseTemplateDetailResult = {
    /** Detail of the requested template, or null while it is loading or failed to load. */
    detail: TemplateDetail | null
    isLoading: boolean
    /** Fetches the detail again, e.g. after the template was edited. */
    reload: () => void
}

/**
 * Loads the detail of the template with the given uuid; an empty uuid loads nothing.
 */
export function useTemplateDetail(uuid: string): UseTemplateDetailResult {
    const [loaded, setLoaded] = useState<TemplateDetail | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [reloadCount, setReloadCount] = useState(0)

    useEffect(() => {
        if (!uuid) {
            setLoaded(null)
            setIsLoading(false)
            return
        }

        let isCurrent = true
        setIsLoading(true)

        getTemplate(uuid)
            .then((detail) => {
                if (isCurrent) {
                    setLoaded(detail)
                }
            })
            .catch(() => {
                if (isCurrent) {
                    setLoaded(null)
                }
            })
            .finally(() => {
                if (isCurrent) {
                    setIsLoading(false)
                }
            })

        return () => {
            isCurrent = false
        }
    }, [uuid, reloadCount])

    const reload = useCallback(() => setReloadCount((count) => count + 1), [])

    return {
        // A detail of the previously requested template must not be shown for the new one.
        detail: loaded?.uuid === uuid ? loaded : null,
        isLoading,
        reload,
    }
}
