import { useState } from 'react'
import { toast } from 'sonner'

import { exportTemplateAsJson } from '@/client'
import { CustomTemplateSection, type EditingTemplate } from '@/components/CustomTemplateSection'
import styles from '@/components/settings/TenantTemplateSettings.module.css'
import { useTemplates } from '@/hooks/useTemplates'
import type { TemplateOption } from '@/types'

export function TenantTemplateSection() {
    const [isCreating, setIsCreating] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EditingTemplate | null>(null)
    const [busyUuid, setBusyUuid] = useState<string | null>(null)

    const { templates, isLoading, upsertSaved, deleteByUuid, loadDetail } = useTemplates({
        scope: 'tenant',
        onLoadError: toast.error,
    })

    const handleSaved = (savedTemplate: TemplateOption) => {
        upsertSaved(savedTemplate)
        setIsCreating(false)
        setEditingTemplate(null)
        toast.success(`Common template "${savedTemplate.title}" was saved.`)
    }

    const handleEdit = async (template: TemplateOption) => {
        setBusyUuid(template.uuid)
        try {
            const detail = await loadDetail(template.uuid)
            setIsCreating(false)
            setEditingTemplate({
                uuid: detail.uuid,
                title: detail.title,
                content: detail.content,
            })
        } catch (editError) {
            toast.error(
                editError instanceof Error ? editError.message : 'Failed to load the template.',
            )
        } finally {
            setBusyUuid(null)
        }
    }

    const handleDelete = async (template: TemplateOption) => {
        setBusyUuid(template.uuid)

        const deleted = await deleteByUuid(template, {
            confirmMessage: `Delete the tenant-wide template "${template.title}"? This cannot be undone.`,
            onError: toast.error,
        })

        if (deleted) {
            if (editingTemplate?.uuid === template.uuid) {
                setEditingTemplate(null)
            }
            toast.success(`Tenant-wide template "${template.title}" was deleted.`)
        }

        setBusyUuid(null)
    }

    const handleExport = async (template: TemplateOption) => {
        setBusyUuid(template.uuid)
        try {
            const blob = await exportTemplateAsJson(template.uuid)
            const fileName = `${template.title}.json`
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
        } finally {
            setBusyUuid(null)
        }
    }

    if (isLoading) {
        return (
            <section className={styles.root}>
                <h4 className={styles.heading}>Common templates</h4>
                <p className={styles.muted}>Loading common templates...</p>
            </section>
        )
    }

    return (
        <section className={styles.root}>
            <div>
                <h4 className={styles.heading}>Common templates</h4>
                <p className={styles.muted}>
                    Templates created here are available to everyone in your tenant.
                </p>
            </div>

            {templates.length === 0 ? (
                <p className={styles.muted}>No common templates yet.</p>
            ) : (
                <ul className={styles.list}>
                    {templates.map((template) => (
                        <li key={template.uuid} className={styles.listItem}>
                            <div className={styles.listItemRow}>
                                <span className={styles.listTitle}>{template.title}</span>
                                <div className={styles.listActions}>
                                    <button
                                        type="button"
                                        className="btn btn-outline-secondary btn-sm with-icon"
                                        onClick={() => void handleEdit(template)}
                                        disabled={
                                            busyUuid !== null ||
                                            editingTemplate?.uuid === template.uuid
                                        }
                                    >
                                        <i className="fas fa-pen" aria-hidden="true" />
                                        Edit
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-outline-secondary btn-sm with-icon"
                                        onClick={() => void handleExport(template)}
                                        disabled={busyUuid !== null}
                                    >
                                        <i className="fas fa-download" aria-hidden="true" />
                                        {busyUuid === template.uuid
                                            ? 'Exporting...'
                                            : 'Export template'}
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-outline-danger btn-sm with-icon"
                                        onClick={() => void handleDelete(template)}
                                        disabled={busyUuid !== null}
                                    >
                                        <i className="fas fa-trash" aria-hidden="true" />
                                        Delete
                                    </button>
                                </div>
                            </div>

                            {editingTemplate?.uuid === template.uuid ? (
                                <CustomTemplateSection
                                    scope="tenant"
                                    editingTemplate={editingTemplate}
                                    onSaved={handleSaved}
                                    onCancel={() => setEditingTemplate(null)}
                                />
                            ) : null}
                        </li>
                    ))}
                </ul>
            )}

            {isCreating ? (
                <CustomTemplateSection
                    scope="tenant"
                    onSaved={handleSaved}
                    onCancel={() => setIsCreating(false)}
                />
            ) : (
                <button
                    type="button"
                    className="btn btn-primary with-icon"
                    onClick={() => {
                        setIsCreating(true)
                        setEditingTemplate(null)
                    }}
                >
                    <i className="fas fa-plus" aria-hidden="true" />
                    Create tenant-wide template
                </button>
            )}
        </section>
    )
}
