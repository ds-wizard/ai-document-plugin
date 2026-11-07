import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { EmptyState } from '@ds-wizard/plugin-sdk/ui/EmptyState'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { List, ListItem } from '@ds-wizard/plugin-sdk/ui/ListItem'
import { Muted, Title } from '@ds-wizard/plugin-sdk/ui/Text'
import { useState } from 'react'
import { toast } from 'sonner'

import { TemplateFormDialog, type TemplateFormTarget } from '@/components/TemplateFormDialog'
import { downloadTemplateJson } from '@/download'
import { useTemplates } from '@/hooks/useTemplates'
import type { TemplateOption } from '@/types'

type BusyAction = { uuid: string; action: 'edit' | 'export' | 'delete' }

export function TenantTemplateSection() {
    const [formTarget, setFormTarget] = useState<TemplateFormTarget | null>(null)
    const [busy, setBusy] = useState<BusyAction | null>(null)

    const { templates, isLoading, upsertSaved, deleteByUuid, loadDetail } = useTemplates({
        scope: 'tenant',
        onLoadError: toast.error,
    })

    const handleSaved = (savedTemplate: TemplateOption) => {
        upsertSaved(savedTemplate)
        setFormTarget(null)
        toast.success(`Common template "${savedTemplate.title}" was saved.`)
    }

    const handleEdit = async (template: TemplateOption) => {
        setBusy({ uuid: template.uuid, action: 'edit' })
        try {
            setFormTarget(await loadDetail(template.uuid))
        } catch (editError) {
            toast.error(
                editError instanceof Error ? editError.message : 'Failed to load the template.',
            )
        } finally {
            setBusy(null)
        }
    }

    const handleDelete = async (template: TemplateOption) => {
        setBusy({ uuid: template.uuid, action: 'delete' })

        const deleted = await deleteByUuid(template, {
            confirmMessage: `Delete the tenant-wide template "${template.title}"? This cannot be undone.`,
            onError: toast.error,
        })

        if (deleted) {
            toast.success(`Tenant-wide template "${template.title}" was deleted.`)
        }

        setBusy(null)
    }

    const handleExport = async (template: TemplateOption) => {
        setBusy({ uuid: template.uuid, action: 'export' })
        await downloadTemplateJson(template)
        setBusy(null)
    }

    const isBusy = (template: TemplateOption, action: BusyAction['action']) =>
        busy?.uuid === template.uuid && busy.action === action

    return (
        <Stack>
            <Stack>
                <Title>Common templates</Title>
                <Muted>Templates created here are available to everyone in your tenant.</Muted>
            </Stack>

            <AsyncBlock loading={isLoading} loadingLabel="Loading common templates...">
                <Stack>
                    {templates.length === 0 ? (
                        <EmptyState
                            headingLevel={3}
                            title="No common templates yet"
                            description="Common templates you create will be listed here."
                        />
                    ) : (
                        <List>
                            {templates.map((template) => (
                                <ListItem
                                    key={template.uuid}
                                    title={template.title}
                                    actions={
                                        <Inline>
                                            <Button
                                                size="small"
                                                icon="fa-pen"
                                                loading={isBusy(template, 'edit')}
                                                disabled={busy !== null}
                                                onClick={() => void handleEdit(template)}
                                            >
                                                Edit
                                            </Button>
                                            <Button
                                                size="small"
                                                icon="fa-download"
                                                loading={isBusy(template, 'export')}
                                                disabled={busy !== null}
                                                onClick={() => void handleExport(template)}
                                            >
                                                {isBusy(template, 'export')
                                                    ? 'Exporting...'
                                                    : 'Export template'}
                                            </Button>
                                            <Button
                                                size="small"
                                                variant="dangerSecondary"
                                                icon="fa-trash"
                                                loading={isBusy(template, 'delete')}
                                                disabled={busy !== null}
                                                onClick={() => void handleDelete(template)}
                                            >
                                                Delete
                                            </Button>
                                        </Inline>
                                    }
                                />
                            ))}
                        </List>
                    )}

                    <Inline>
                        <Button
                            variant="primary"
                            icon="fa-plus"
                            onClick={() => setFormTarget('new')}
                        >
                            Create tenant-wide template
                        </Button>
                    </Inline>
                </Stack>
            </AsyncBlock>

            {formTarget ? (
                <TemplateFormDialog
                    scope="tenant"
                    target={formTarget}
                    onSaved={handleSaved}
                    onClose={() => setFormTarget(null)}
                />
            ) : null}
        </Stack>
    )
}
