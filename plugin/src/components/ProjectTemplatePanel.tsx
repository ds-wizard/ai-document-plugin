import { useCallback, useEffect, useState } from 'react'

import { LanguageDropdown } from '@/components/LanguageDropdown'
import styles from '@/components/ProjectTemplatePanel.module.css'
import { TemplateDropdown } from '@/components/TemplateDropdown'
import { TemplateManager } from '@/components/TemplateManager'
import type { LanguageOption } from '@/data/languages'
import type { UseTemplatesResult } from '@/hooks/useTemplates'

type ProjectTemplatePanelProps = {
    templates: UseTemplatesResult
    disabled: boolean
    onSelectedUuidChange: (uuid: string) => void
    language: string
    languageOptions: LanguageOption[]
    languagesLoading: boolean
    onLanguageChange: (language: string) => void
}

/**
 * Project-tab template UI: selection, preview, and personal create/edit/delete.
 * Data comes from {@link useTemplates}; this component owns the dropdown selection.
 */
export function ProjectTemplatePanel({
    templates,
    disabled,
    onSelectedUuidChange,
    language,
    languageOptions,
    languagesLoading,
    onLanguageChange,
}: ProjectTemplatePanelProps) {
    const { templates: options, isLoading, upsertSaved, deleteByUuid } = templates

    const [selectedUuid, setSelectedUuid] = useState('')
    const [isCreating, setIsCreating] = useState(false)

    useEffect(() => {
        onSelectedUuidChange(selectedUuid)
    }, [selectedUuid, onSelectedUuidChange])

    const select = useCallback((uuid: string) => {
        setSelectedUuid(uuid)
    }, [])

    const startCreating = useCallback(() => {
        setIsCreating(true)
    }, [])

    return (
        <>
            <div className={styles.selector}>
                <h4>Generate DMP from your questionnaire</h4>
                <div className={styles.languageControl}>
                    <LanguageDropdown
                        options={languageOptions}
                        value={language}
                        onChange={onLanguageChange}
                        disabled={disabled || languageOptions.length === 0}
                        loading={languagesLoading}
                    />
                </div>
                <TemplateDropdown
                    value={selectedUuid}
                    onChange={select}
                    templates={options}
                    onCreate={startCreating}
                    isLoading={isLoading}
                    disabled={disabled}
                />
            </div>

            <TemplateManager
                selectedUuid={selectedUuid}
                templates={options}
                isLoading={isLoading}
                isCreating={isCreating}
                upsertSaved={upsertSaved}
                deleteByUuid={deleteByUuid}
                onSelectedUuidChange={setSelectedUuid}
                onCreatingChange={setIsCreating}
            />
        </>
    )
}
