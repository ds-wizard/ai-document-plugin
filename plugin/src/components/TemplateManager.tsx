import { useCallback, useEffect, useState } from 'react'

import { getTemplate } from '@/client'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import styles from '@/components/TemplateManager.module.css'
import { TemplatePreview } from '@/components/TemplatePreview'
import type { UseTemplatesResult } from '@/hooks/useTemplates'
import type { TemplateDetail, TemplateOption } from '@/types'

type TemplateManagerProps = {
    selectedUuid: string
    templates: TemplateOption[]
    isLoading: boolean
    disabled: boolean
    isDeleting: boolean
    upsertSaved: UseTemplatesResult['upsertSaved']
    deleteByUuid: UseTemplatesResult['deleteByUuid']
    notifySuccess: (message: string) => void
    notifyError: (message: string) => void
    onSelectedUuidChange: (uuid: string) => void
}

/**
 * Preview and personal create/edit/delete for the selected template.
 */
export function TemplateManager({
    selectedUuid,
    templates,
    isLoading,
    disabled,
    isDeleting,
    upsertSaved,
    deleteByUuid,
    notifySuccess,
    notifyError,
    onSelectedUuidChange,
}: TemplateManagerProps) {
    const [isCreating, setIsCreating] = useState(false)
    const [isEditing, setIsEditing] = useState(false)
    const [detail, setDetail] = useState<TemplateDetail | null>(null)
    const [isLoadingDetail, setIsLoadingDetail] = useState(false)

    const selected = templates.find((template) => template.uuid === selectedUuid)
    const canManageSelected = selected?.scope === 'personal'
    const showPreview = Boolean(selectedUuid) && !isCreating && !isLoading

    useEffect(() => {
        if (!showPreview) {
            setDetail(null)
            setIsLoadingDetail(false)
            return
        }

        if (detail?.uuid === selectedUuid) {
            return
        }

        let isMounted = true

        const loadDetail = async () => {
            setIsLoadingDetail(true)

            try {
                const loaded = await getTemplate(selectedUuid)
                if (isMounted) {
                    setDetail(loaded)
                }
            } catch {
                if (isMounted) {
                    setDetail(null)
                }
            } finally {
                if (isMounted) {
                    setIsLoadingDetail(false)
                }
            }
        }

        void loadDetail()

        return () => {
            isMounted = false
        }
    }, [detail?.uuid, selectedUuid, showPreview])

    const resetDetail = useCallback(() => setDetail(null), [])

    const isEditingSelected = isEditing && detail !== null && detail.uuid === selectedUuid
    const isDetailForSelected = detail?.uuid === selectedUuid
    const showActions =
        showPreview && canManageSelected && !isEditingSelected && isDetailForSelected
    const showCreateButton = !isCreating && !isEditingSelected

    useEffect(() => {
        if (selectedUuid) {
            setIsCreating(false)
            setIsEditing(false)
        }
    }, [selectedUuid])

    const startCreating = useCallback(() => {
        onSelectedUuidChange('')
        setIsEditing(false)
        setIsCreating(true)
    }, [onSelectedUuidChange])

    const cancelCreating = useCallback(() => {
        setIsCreating(false)
    }, [])

    const startEditing = useCallback(() => {
        setIsEditing(true)
    }, [])

    const cancelEditing = useCallback(() => {
        setIsEditing(false)
    }, [])

    const handleSaved = useCallback(
        (saved: TemplateOption) => {
            upsertSaved(saved)
            onSelectedUuidChange(saved.uuid)
            resetDetail()
            setIsEditing(false)
            setIsCreating(false)
            notifySuccess(`Template "${saved.title}" was saved.`)
        },
        [upsertSaved, onSelectedUuidChange, resetDetail, notifySuccess],
    )

    const handleDelete = useCallback(async () => {
        if (!selected || selected.scope !== 'personal') {
            return
        }

        const deleted = await deleteByUuid(selected, {
            confirmMessage: `Delete the template "${selected.title}"? This cannot be undone.`,
            onError: notifyError,
        })

        if (deleted) {
            onSelectedUuidChange('')
            resetDetail()
            setIsEditing(false)
            notifySuccess(`Template "${selected.title}" was deleted.`)
        }
    }, [selected, deleteByUuid, onSelectedUuidChange, resetDetail, notifySuccess, notifyError])

    return (
        <>
            {detail && !isEditingSelected ? (
                <TemplatePreview
                    content={isDetailForSelected ? detail.content : undefined}
                    isLoading={isLoadingDetail || !isDetailForSelected}
                />
            ) : null}

            {showActions ? (
                <div className={styles.templateActions}>
                    <button
                        type="button"
                        className="btn btn-outline-secondary with-icon"
                        onClick={startEditing}
                        disabled={isDeleting}
                    >
                        <i className="fas fa-pen" aria-hidden="true" />
                        Edit template
                    </button>
                    <button
                        type="button"
                        className="btn btn-outline-danger with-icon"
                        onClick={() => void handleDelete()}
                        disabled={isDeleting}
                    >
                        <i className="fas fa-trash" aria-hidden="true" />
                        {isDeleting ? 'Deleting...' : 'Delete template'}
                    </button>
                </div>
            ) : null}

            {showCreateButton ? (
                <button
                    type="button"
                    className={`btn btn-link with-icon ${styles.createTemplateButton}`}
                    onClick={startCreating}
                    disabled={isLoading || disabled}
                >
                    <i className="fas fa-plus" aria-hidden="true" />
                    Create your own template
                </button>
            ) : null}

            {isEditingSelected && detail ? (
                <CustomTemplateSection
                    scope="personal"
                    editingTemplate={{
                        uuid: detail.uuid,
                        title: detail.title,
                        content: detail.content,
                    }}
                    onSaved={handleSaved}
                    onCancel={cancelEditing}
                />
            ) : null}

            {isCreating ? (
                <CustomTemplateSection
                    scope="personal"
                    onSaved={handleSaved}
                    onCancel={cancelCreating}
                />
            ) : null}
        </>
    )
}
