import styles from '@/components/TemplatePreview.module.css'
import type { ApiTemplateContent, ApiTemplateSection } from '@/types'

type TemplatePreviewProps = {
    content?: ApiTemplateContent
    isLoading: boolean
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

export function TemplatePreview({ content, isLoading }: TemplatePreviewProps) {
    const sections = content?.sections ?? []

    return (
        <section className={styles.root} aria-label="Template preview">
            <div className={styles.label}>
                <span className={styles.labelText}>Template preview</span>
                <div className={styles.content}>
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
