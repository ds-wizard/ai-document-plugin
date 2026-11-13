import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { IconButton } from '@ds-wizard/plugin-sdk/ui/Button'
import { Card } from '@ds-wizard/plugin-sdk/ui/Card'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Muted, Subtitle } from '@ds-wizard/plugin-sdk/ui/Text'
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
        <section aria-label="Template preview">
            <Card>
                <Stack>
                    <Inline align="between">
                        <Subtitle>Template preview:</Subtitle>
                        {canManage ? (
                            <Inline>
                                <IconButton
                                    icon="fa-pen"
                                    label="Edit template"
                                    tooltip
                                    size="small"
                                    disabled={isBusy}
                                    onClick={onEdit}
                                />
                                <IconButton
                                    icon="fa-download"
                                    label="Export template"
                                    tooltip
                                    size="small"
                                    loading={busyAction === 'export'}
                                    disabled={isBusy}
                                    onClick={() => void runAction('export', onExport)}
                                />
                                <IconButton
                                    icon="fa-trash"
                                    label="Delete template"
                                    tooltip
                                    size="small"
                                    variant="dangerSecondary"
                                    loading={busyAction === 'delete'}
                                    disabled={isBusy}
                                    onClick={() => void runAction('delete', onDelete)}
                                />
                            </Inline>
                        ) : null}
                    </Inline>
                    {hasCoverPage ? (
                        <CoverPagePreview embedded />
                    ) : null}
                    <div className={styles.scrollList}>
                        <AsyncBlock
                            loading={isLoading}
                            loadingLabel="Loading template structure..."
                        >
                            {sections.length === 0 ? (
                                <Muted>This template has no sections.</Muted>
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
                        </AsyncBlock>
                    </div>
                </Stack>
            </Card>
        </section>
    )
}
