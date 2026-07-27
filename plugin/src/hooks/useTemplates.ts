import { useCallback, useEffect, useState } from 'react'

import { deleteTemplate, getTemplate, getTemplates } from '@/client'
import type { TemplateDetail, TemplateOption, TemplateScope } from '@/types'

const byTitle = (left: TemplateOption, right: TemplateOption) =>
    left.title.localeCompare(right.title)

const mergeSaved = (current: TemplateOption[], saved: TemplateOption): TemplateOption[] =>
    [saved, ...current.filter((template) => template.uuid !== saved.uuid)].sort(byTitle)

const filterByScope = (
    templates: TemplateOption[],
    scope: TemplateScope | 'all',
): TemplateOption[] =>
    scope === 'all' ? templates : templates.filter((template) => template.scope === scope)

export type UseTemplatesOptions = {
    /** Which templates to keep after loading. Defaults to `all`. */
    scope?: TemplateScope | 'all'
    /** When this value changes the list is reloaded. */
    reloadKey?: unknown
    /** Called when loading starts, if set (e.g. to clear prior messages). */
    onReload?: () => void
    /** Called with a user-facing message when loading fails. */
    onLoadError?: (message: string) => void
}

export type DeleteTemplateOptions = {
    confirmMessage: string
    successMessage?: string
    onSuccess?: () => void
    onError?: (message: string) => void
}

export type UseTemplatesResult = {
    templates: TemplateOption[]
    isLoading: boolean
    isDeleting: boolean
    upsertSaved: (saved: TemplateOption) => void
    removeFromList: (uuid: string) => void
    deleteByUuid: (template: TemplateOption, options: DeleteTemplateOptions) => Promise<boolean>
    loadDetail: (uuid: string) => Promise<TemplateDetail>
    refresh: () => Promise<void>
}

const loadErrorMessage = (error: unknown, fallback: string): string => {
    if (error instanceof TypeError) {
        return 'Cannot connect to the server.'
    }
    if (error instanceof Error) {
        return error.message
    }
    return fallback
}

/**
 * Shared template data: list loading, detail fetch, save merge, and delete.
 * UI state (selection, create/edit modes, preview toggles) belongs in components.
 */
export function useTemplates({
    scope = 'all',
    reloadKey,
    onReload,
    onLoadError,
}: UseTemplatesOptions = {}): UseTemplatesResult {
    const [templates, setTemplates] = useState<TemplateOption[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [isDeleting, setIsDeleting] = useState(false)

    const refresh = useCallback(async () => {
        setIsLoading(true)
        onReload?.()

        try {
            const loaded = await getTemplates()
            setTemplates(filterByScope(loaded, scope))
        } catch (error) {
            onLoadError?.(
                loadErrorMessage(
                    error,
                    scope === 'tenant'
                        ? 'Failed to load common templates.'
                        : 'Unable to load the list of templates.',
                ),
            )
        } finally {
            setIsLoading(false)
        }
    }, [scope, onReload, onLoadError])

    useEffect(() => {
        let isMounted = true

        const load = async () => {
            setIsLoading(true)
            onReload?.()

            try {
                const loaded = await getTemplates()
                if (!isMounted) {
                    return
                }
                setTemplates(filterByScope(loaded, scope))
            } catch (error) {
                if (!isMounted) {
                    console.error(error)
                    return
                }
                onLoadError?.(
                    loadErrorMessage(
                        error,
                        scope === 'tenant'
                            ? 'Failed to load common templates.'
                            : 'Unable to load the list of templates.',
                    ),
                )
            } finally {
                if (isMounted) {
                    setIsLoading(false)
                }
            }
        }

        void load()

        return () => {
            isMounted = false
        }
    }, [scope, reloadKey, onReload, onLoadError])

    const upsertSaved = useCallback((saved: TemplateOption) => {
        setTemplates((current) => mergeSaved(current, saved))
    }, [])

    const removeFromList = useCallback((uuid: string) => {
        setTemplates((current) => current.filter((template) => template.uuid !== uuid))
    }, [])

    const loadDetail = useCallback(async (uuid: string): Promise<TemplateDetail> => {
        return getTemplate(uuid)
    }, [])

    const deleteByUuid = useCallback(
        async (template: TemplateOption, options: DeleteTemplateOptions): Promise<boolean> => {
            if (!window.confirm(options.confirmMessage)) {
                return false
            }

            setIsDeleting(true)
            try {
                await deleteTemplate(template.uuid)
                removeFromList(template.uuid)
                options.onSuccess?.()
                return true
            } catch (error) {
                const message =
                    error instanceof Error ? error.message : 'Failed to delete the template.'
                options.onError?.(message)
                return false
            } finally {
                setIsDeleting(false)
            }
        },
        [removeFromList],
    )

    return {
        templates,
        isLoading,
        isDeleting,
        upsertSaved,
        removeFromList,
        deleteByUuid,
        loadDetail,
        refresh,
    }
}
