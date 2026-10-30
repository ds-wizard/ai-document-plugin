import { useState } from 'react'

import { CoverPagePreview } from '@/components/CoverPagePreview'
import styles from '@/components/TemplatePreview.module.css'
import type { ApiTemplateContent, ApiTemplateSection } from '@/types'

type TemplatePreviewProps = {
    content?: ApiTemplateContent
    isLoading: boolean
    hasCoverPage?: boolean
    canManage: boolean
    onEdit: () => void
    onExport: () => Promise<void>
    onDelete: () => Promise<void>
}

type PreviewSectionNodeProps = {
    section: ApiTemplateSection
    depth: number
    path: string
}

function depthClassName(depth: number): string {
    return depth === 0 ? styles.depthTop : styles.depthNested
}

function displayTitle(title: string): string {
    return title.trim() || 'Untitled section'
}

function PreviewSectionNode({ section, depth, path }: PreviewSectionNodeProps) {
    const childSections = section.sections ?? []

    return (
        <li className={styles.item}>
            <span className={depthClassName(depth)}>{displayTitle(section.title)}</span>
            {childSections.length > 0 ? (
                <ul className={styles.nestedList}>
                    {childSections.map((child, childIndex) => (
                        <PreviewSectionNode
                            key={`${path}.${childIndex}`}
                            section={child}
                            depth={depth + 1}
                            path={`${path}.${childIndex}`}
                        />
                    ))}
                </ul>
            ) : null}
        </li>
    )
}

export function TemplatePreview({
    content,
    isLoading,
    hasCoverPage = false,
    canManage,
    onEdit,
    onExport,
    onDelete,
}: TemplatePreviewProps) {
    const sections = content?.sections ?? []
    const [busyAction, setBusyAction] = useState<'export' | 'delete' | null>(null)

    const runAction = async (action: 'export' | 'delete', run: () => Promise<void>) => {
        setBusyAction(action)
        try {
            await run()
        } finally {
            setBusyAction(null)
        }
    }

    const isBusy = busyAction !== null

    return (
        <section className="ai-doc-card" aria-label="Template preview">
            <div className={styles.label}>
                <div className={styles.header}>
                    <h5 className="ai-doc-title">Template preview:</h5>
                    {canManage ? (
                        <div className={styles.actions}>
                            <button
                                type="button"
                                className="btn btn-outline-secondary btn-sm"
                                onClick={onEdit}
                                disabled={isBusy}
                                title="Edit template"
                                aria-label="Edit template"
                            >
                                <i className="fas fa-pen" aria-hidden="true" />
                            </button>
                            <button
                                type="button"
                                className="btn btn-outline-secondary btn-sm"
                                onClick={() => void runAction('export', onExport)}
                                disabled={isBusy}
                                title="Export template"
                                aria-label="Export template"
                            >
                                <i
                                    className={
                                        busyAction === 'export'
                                            ? 'fas fa-spinner fa-spin'
                                            : 'fas fa-download'
                                    }
                                    aria-hidden="true"
                                />
                            </button>
                            <button
                                type="button"
                                className="btn btn-outline-danger btn-sm"
                                onClick={() => void runAction('delete', onDelete)}
                                disabled={isBusy}
                                title="Delete template"
                                aria-label="Delete template"
                            >
                                <i
                                    className={
                                        busyAction === 'delete'
                                            ? 'fas fa-spinner fa-spin'
                                            : 'fas fa-trash'
                                    }
                                    aria-hidden="true"
                                />
                            </button>
                        </div>
                    ) : null}
                </div>
                {hasCoverPage ? <CoverPagePreview embedded /> : null}
                <div className="ai-doc-scroll-list">
                    {isLoading ? (
                        <p className={styles.status}>Loading template structure...</p>
                    ) : sections.length === 0 ? (
                        <p className={styles.status}>This template has no sections.</p>
                    ) : (
                        <ul className={styles.sectionList}>
                            {sections.map((section, sectionIndex) => (
                                <PreviewSectionNode
                                    key={String(sectionIndex)}
                                    section={section}
                                    depth={0}
                                    path={String(sectionIndex)}
                                />
                            ))}
                        </ul>
                    )}
                </div>
            </div>
        </section>
    )
}
