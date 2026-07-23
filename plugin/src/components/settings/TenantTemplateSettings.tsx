import { useCallback, useState } from 'react'

import { CustomTemplateSection, type EditingTemplate } from '@/components/CustomTemplateSection'
import { FeedbackAlert } from '@/components/FeedbackAlert'
import styles from '@/components/settings/TenantTemplateSettings.module.css'
import { useTemplates } from '@/hooks/useTemplates'
import type { TemplateOption } from '@/types'

export function TenantTemplateSection() {
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [isCreating, setIsCreating] = useState(false)
    const [editingTemplate, setEditingTemplate] = useState<EditingTemplate | null>(null)
    const [busyUuid, setBusyUuid] = useState<string | null>(null)

    const handleReload = useCallback(() => {
        setError(null)
    }, [])

    const handleLoadError = useCallback((message: string) => {
        setError(message)
    }, [])

    const { templates, isLoading, upsertSaved, deleteByUuid, loadDetail } = useTemplates({
        scope: 'tenant',
        onReload: handleReload,
        onLoadError: handleLoadError,
    })

    const handleSaved = (savedTemplate: TemplateOption) => {
        upsertSaved(savedTemplate)
        setIsCreating(false)
        setEditingTemplate(null)
        setError(null)
        setSuccess(`Common template "${savedTemplate.title}" was saved.`)
    }

    const handleEdit = async (template: TemplateOption) => {
        setBusyUuid(template.uuid)
        setError(null)
        try {
            const detail = await loadDetail(template.uuid)
            setIsCreating(false)
            setEditingTemplate({
                uuid: detail.uuid,
                title: detail.title,
                content: detail.content,
            })
        } catch (editError) {
            setError(
                editError instanceof Error ? editError.message : 'Failed to load the template.',
            )
        } finally {
            setBusyUuid(null)
        }
    }

    const handleDelete = async (template: TemplateOption) => {
        setBusyUuid(template.uuid)
        setError(null)

        const deleted = await deleteByUuid(template, {
            confirmMessage: `Delete the tenant-wide template "${template.title}"? This cannot be undone.`,
            onError: (message) => setError(message),
        })

        if (deleted) {
            if (editingTemplate?.uuid === template.uuid) {
                setEditingTemplate(null)
            }
            setSuccess(`Tenant-wide template "${template.title}" was deleted.`)
        }

        setBusyUuid(null)
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

            {error ? <FeedbackAlert kind="error">{error}</FeedbackAlert> : null}
            {success ? <FeedbackAlert kind="success">{success}</FeedbackAlert> : null}

            {templates.length === 0 ? (
                <p className={styles.muted}>No common templates yet.</p>
            ) : (
                <ul className={styles.list}>
                    {templates.map((template) => (
                        <li key={template.uuid} className={styles.listItem}>
                            <span className={styles.listTitle}>{template.title}</span>
                            <div className={styles.listActions}>
                                <button
                                    type="button"
                                    className="btn btn-outline-secondary btn-sm with-icon"
                                    onClick={() => void handleEdit(template)}
                                    disabled={busyUuid !== null}
                                >
                                    <i className="fas fa-pen" aria-hidden="true" />
                                    Edit
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
                        </li>
                    ))}
                </ul>
            )}

            {(() => {
                if (editingTemplate) {
                    return (
                        <CustomTemplateSection
                            scope="tenant"
                            editingTemplate={editingTemplate}
                            onSaved={handleSaved}
                            onCancel={() => setEditingTemplate(null)}
                        />
                    )
                } else if (isCreating) {
                    return (
                        <CustomTemplateSection
                            scope="tenant"
                            onSaved={handleSaved}
                            onCancel={() => setIsCreating(false)}
                        />
                    )
                } else {
                    return (
                        <button
                            type="button"
                            className="btn btn-primary with-icon"
                            onClick={() => {
                                setIsCreating(true)
                                setSuccess(null)
                            }}
                        >
                            <i className="fas fa-plus" aria-hidden="true" />
                            Create tenant-wide template
                        </button>
                    )
                }
            })()}
        </section>
    )
}
