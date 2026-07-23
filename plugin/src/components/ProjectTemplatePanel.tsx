import { useCallback, useEffect, useState } from 'react'

import styles from '@/components/ProjectTemplatePanel.module.css'
import { TemplateDropdown } from '@/components/TemplateDropdown'
import { TemplateManager } from '@/components/TemplateManager'
import type { FeedbackController } from '@/hooks/useFeedback'
import type { UseTemplatesResult } from '@/hooks/useTemplates'

type ProjectTemplatePanelProps = {
    templates: UseTemplatesResult
    feedback: FeedbackController
    disabled: boolean
    onSelectedUuidChange: (uuid: string) => void
}

/**
 * Project-tab template UI: selection, preview, and personal create/edit/delete.
 * Data comes from {@link useTemplates}; this component owns the dropdown selection.
 */
export function ProjectTemplatePanel({
    templates,
    feedback,
    disabled,
    onSelectedUuidChange,
}: ProjectTemplatePanelProps) {
    const { notifySuccess, notifyError } = feedback
    const { templates: options, isLoading, isDeleting, upsertSaved, deleteByUuid } = templates

    const [selectedUuid, setSelectedUuid] = useState('')

    useEffect(() => {
        onSelectedUuidChange(selectedUuid)
    }, [selectedUuid, onSelectedUuidChange])

    const select = useCallback((uuid: string) => {
        setSelectedUuid(uuid)
    }, [])

    return (
        <>
            <div className={styles.selector}>
                <h4>DMP template</h4>
                <TemplateDropdown
                    value={selectedUuid}
                    onChange={select}
                    templates={options}
                    isLoading={isLoading}
                    disabled={disabled}
                />
            </div>

            <TemplateManager
                selectedUuid={selectedUuid}
                templates={options}
                isLoading={isLoading}
                disabled={disabled}
                isDeleting={isDeleting}
                upsertSaved={upsertSaved}
                deleteByUuid={deleteByUuid}
                notifySuccess={notifySuccess}
                notifyError={notifyError}
                onSelectedUuidChange={setSelectedUuid}
            />
        </>
    )
}
