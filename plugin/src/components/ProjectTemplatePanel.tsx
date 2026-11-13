import { Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Title } from '@ds-wizard/plugin-sdk/ui/Text'
import { useState } from 'react'
import { toast } from 'sonner'

import { LanguageDropdown } from '@/components/LanguageDropdown'
import { TemplateDropdown } from '@/components/TemplateDropdown'
import { TemplateFormDialog, type TemplateFormTarget } from '@/components/TemplateFormDialog'
import { TemplatePreview } from '@/components/TemplatePreview'
import type { LanguageOption } from '@/data/languages'
import { downloadTemplateJson } from '@/download'
import { useTemplateDetail } from '@/hooks/useTemplateDetail'
import type { UseTemplatesResult } from '@/hooks/useTemplates'
import type { TemplateOption } from '@/types'

type ProjectTemplatePanelProps = {
    templates: UseTemplatesResult
    selectedUuid: string
    onSelectedUuidChange: (uuid: string) => void
    disabled: boolean
    language: string
    languageOptions: LanguageOption[]
    languagesLoading: boolean
    onLanguageChange: (language: string) => void
}

/**
 * Project-tab template UI: language and template selection, preview of the selected
 * template, and create/edit/export/delete of personal templates.
 */
export function ProjectTemplatePanel({
    templates,
    selectedUuid,
    onSelectedUuidChange,
    disabled,
    language,
    languageOptions,
    languagesLoading,
    onLanguageChange,
}: ProjectTemplatePanelProps) {
    const { templates: options, isLoading, upsertSaved, deleteByUuid } = templates
    const {
        detail,
        isLoading: isDetailLoading,
        reload: reloadDetail,
    } = useTemplateDetail(selectedUuid)
    const [formTarget, setFormTarget] = useState<TemplateFormTarget | null>(null)

    const handleSaved = (saved: TemplateOption) => {
        upsertSaved(saved)
        onSelectedUuidChange(saved.uuid)
        reloadDetail()
        setFormTarget(null)
        toast.success(`Template "${saved.title}" was saved.`)
    }

    const handleExport = async () => {
        if (detail) {
            await downloadTemplateJson(detail)
        }
    }

    const handleDelete = async () => {
        if (!detail) {
            return
        }

        const deleted = await deleteByUuid(detail, {
            confirmMessage: `Delete the template "${detail.title}"? This cannot be undone.`,
            onError: toast.error,
        })

        if (deleted) {
            onSelectedUuidChange('')
            toast.success(`Template "${detail.title}" was deleted.`)
        }
    }

    return (
        <>
            <Stack>
                <Title>Generate DMP from your questionnaire</Title>
                <LanguageDropdown
                    options={languageOptions}
                    value={language}
                    onChange={onLanguageChange}
                    disabled={disabled || languageOptions.length === 0}
                    loading={languagesLoading}
                />
                <TemplateDropdown
                    value={selectedUuid}
                    onChange={onSelectedUuidChange}
                    templates={options}
                    onCreate={() => setFormTarget('new')}
                    isLoading={isLoading}
                    disabled={disabled}
                />
            </Stack>

            {detail || isDetailLoading ? (
                <TemplatePreview
                    language={language}
                    content={detail?.content}
                    isLoading={isDetailLoading}
                    hasCoverPage={detail?.hasCoverPage}
                    canManage={detail?.scope === 'personal'}
                    onEdit={() => setFormTarget(detail)}
                    onExport={handleExport}
                    onDelete={handleDelete}
                />
            ) : null}

            {formTarget ? (
                <TemplateFormDialog
                    language={language}
                    scope="personal"
                    target={formTarget}
                    onSaved={handleSaved}
                    onClose={() => setFormTarget(null)}
                />
            ) : null}
        </>
    )
}
