import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { exportTemplateAsJson, getTemplate } from '@/client'
import { CustomTemplateSection } from '@/components/CustomTemplateSection'
import { TemplatePreview } from '@/components/TemplatePreview'
import type { UseTemplatesResult } from '@/hooks/useTemplates'
import type { TemplateDetail, TemplateOption } from '@/types'

type TemplateManagerProps = {
    selectedUuid: string
    templates: TemplateOption[]
    isLoading: boolean
    isCreating: boolean
    upsertSaved: UseTemplatesResult['upsertSaved']
    deleteByUuid: UseTemplatesResult['deleteByUuid']
    onSelectedUuidChange: (uuid: string) => void
    onCreatingChange: (isCreating: boolean) => void
}

/**
 * Preview and personal create/edit/delete for the selected template.
 */
export function TemplateManager({
    selectedUuid,
    templates,
    isLoading,
    isCreating,
    upsertSaved,
    deleteByUuid,
    onSelectedUuidChange,
    onCreatingChange,
}: TemplateManagerProps) {
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

    useEffect(() => {
        if (selectedUuid) {
            onCreatingChange(false)
            setIsEditing(false)
        }
    }, [selectedUuid, onCreatingChange])

    useEffect(() => {
        if (isCreating) {
            setIsEditing(false)
        }
    }, [isCreating])

    const cancelCreating = useCallback(() => {
        onCreatingChange(false)
    }, [onCreatingChange])

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
            onCreatingChange(false)
            toast.success(`Template "${saved.title}" was saved.`)
        },
        [upsertSaved, onSelectedUuidChange, onCreatingChange, resetDetail],
    )

    const handleDelete = useCallback(async () => {
        if (!selected || selected.scope !== 'personal') {
            return
        }

        const deleted = await deleteByUuid(selected, {
            confirmMessage: `Delete the template "${selected.title}"? This cannot be undone.`,
            onError: toast.error,
        })

        if (deleted) {
            onSelectedUuidChange('')
            resetDetail()
            setIsEditing(false)
            toast.success(`Template "${selected.title}" was deleted.`)
        }
    }, [selected, deleteByUuid, onSelectedUuidChange, resetDetail])

    const handleExport = useCallback(async () => {
        if (!selected) {
            return
        }

        try {
            const blob = await exportTemplateAsJson(selected.uuid)
            const fileName = `${selected.title}.json`
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = fileName
            document.body.appendChild(link)
            link.click()
            link.remove()
            URL.revokeObjectURL(url)
            toast.success('Template JSON download has started.')
        } catch (exportError) {
            toast.error(
                exportError instanceof Error
                    ? exportError.message
                    : 'Failed to export the template as JSON.',
            )
        }
    }, [selected])

    return (
        <>
            {detail && !isEditingSelected ? (
                <TemplatePreview
                    content={isDetailForSelected ? detail.content : undefined}
                    isLoading={isLoadingDetail || !isDetailForSelected}
                    hasCoverPage={detail.hasCoverPage}
                    canManage={showActions}
                    onEdit={startEditing}
                    onExport={handleExport}
                    onDelete={handleDelete}
                />
            ) : null}

            {isEditingSelected && detail ? (
                <CustomTemplateSection
                    key={detail.uuid}
                    scope="personal"
                    editingTemplate={{
                        uuid: detail.uuid,
                        title: detail.title,
                        content: detail.content,
                        hasCoverPage: detail.hasCoverPage,
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
