import { useCallback, useEffect, useRef, useState } from 'react'

import styles from '@/components/TemplateStructureEditor.module.css'
import {
    addChildSectionAtPath,
    getLastAddedChildId,
    getSectionAtPath,
    parseTemplateJson,
    removeSectionAtPath,
    type SectionPath,
    serializeTemplateContent,
    type TemplateSection,
    updateSectionAtPath,
} from '@/data/template-structure'

type TemplateStructureEditorProps = {
    value: string
    onChange: (json: string) => void
}

type SectionNodeEditorProps = {
    section: TemplateSection
    path: SectionPath
    depth: number
    isEditing: boolean
    isSectionEditing: (sectionId: string) => boolean
    onUpdate: (path: SectionPath, patch: Partial<TemplateSection>) => void
    onRemove: (path: SectionPath) => void
    onAddChild: (parentPath: SectionPath) => void
    onStartEditing: (sectionId: string) => void
    onStopEditing: (sectionId: string) => void
}

function sectionAriaLabel(path: SectionPath): string {
    return `section ${path.map((index) => index + 1).join('.')}`
}

function displayTitle(title: string): string {
    return title.trim() || 'Untitled section'
}

function SectionNodeEditor({
    section,
    path,
    depth,
    isEditing,
    isSectionEditing,
    onUpdate,
    onRemove,
    onAddChild,
    onStartEditing,
    onStopEditing,
}: SectionNodeEditorProps) {
    const label = sectionAriaLabel(path)

    return (
        <li
            className={`${styles.sectionCard} ${
                depth % 2 === 1 ? styles.sectionCardTinted : ''
            } ${isEditing ? '' : styles.sectionCardCollapsed}`}
        >
            {isEditing ? (
                <div className={styles.sectionFields}>
                    <label className={styles.field}>
                        <span className={styles.fieldLabel}>Title</span>
                        <input
                            type="text"
                            value={section.title}
                            onChange={(event) => onUpdate(path, { title: event.target.value })}
                            placeholder="Section title"
                            className="form-control"
                        />
                    </label>

                    <label className={styles.field}>
                        <span className={styles.fieldLabel}>Description</span>
                        <textarea
                            value={section.description}
                            onChange={(event) =>
                                onUpdate(path, { description: event.target.value })
                            }
                            placeholder="Section description or guidance"
                            className={`form-control ${styles.descriptionField}`}
                        />
                    </label>
                </div>
            ) : (
                <div className={styles.sectionSummary}>
                    <p className={styles.sectionTitle}>{displayTitle(section.title)}</p>
                    {section.description.trim() ? (
                        <p className={styles.sectionDescription}>{section.description}</p>
                    ) : null}
                </div>
            )}

            <div className={styles.sectionActions}>
                {isEditing ? (
                    <>
                        <button
                            type="button"
                            className="btn btn-outline-secondary with-icon"
                            onClick={() => onAddChild(path)}
                        >
                            <i className="fas fa-plus" aria-hidden="true" />
                            Add subsection
                        </button>
                        <div className={styles.sectionActionsEnd}>
                            <button
                                type="button"
                                className={`btn btn-outline-secondary ${styles.iconButton}`}
                                onClick={() => onRemove(path)}
                                aria-label={`Remove ${label}`}
                            >
                                <i className="fas fa-trash" aria-hidden="true" />
                            </button>
                            <button
                                type="button"
                                className="btn btn-primary btn-wide with-icon"
                                onClick={() => onStopEditing(section.id)}
                                aria-label={`Finish editing ${label}`}
                            >
                                <i className="fas fa-check" aria-hidden="true" />
                                Confirm
                            </button>
                        </div>
                    </>
                ) : (
                    <div className={styles.sectionActionsEnd}>
                        <button
                            type="button"
                            className={`btn btn-outline-secondary ${styles.iconButton}`}
                            onClick={() => onRemove(path)}
                            aria-label={`Remove ${label}`}
                        >
                            <i className="fas fa-trash" aria-hidden="true" />
                        </button>
                        <button
                            type="button"
                            className={`btn btn-outline-secondary ${styles.iconButton}`}
                            onClick={() => onStartEditing(section.id)}
                            aria-label={`Edit ${label}`}
                        >
                            <i className="fas fa-pen" aria-hidden="true" />
                        </button>
                    </div>
                )}
            </div>

            {section.sections.length > 0 ? (
                <ul className={styles.nestedSectionList}>
                    {section.sections.map((child, childIndex) => (
                        <SectionNodeEditor
                            key={child.id}
                            section={child}
                            path={[...path, childIndex]}
                            depth={depth + 1}
                            isEditing={isSectionEditing(child.id)}
                            isSectionEditing={isSectionEditing}
                            onUpdate={onUpdate}
                            onRemove={onRemove}
                            onAddChild={onAddChild}
                            onStartEditing={onStartEditing}
                            onStopEditing={onStopEditing}
                        />
                    ))}
                </ul>
            ) : null}
        </li>
    )
}

export function TemplateStructureEditor({ value, onChange }: TemplateStructureEditorProps) {
    const [sections, setSections] = useState<TemplateSection[]>(
        () => parseTemplateJson(value)?.sections ?? [],
    )
    const [parseWarning, setParseWarning] = useState(false)
    const [editingSectionIds, setEditingSectionIds] = useState<Set<string>>(() => new Set())
    const skipExternalSync = useRef(false)

    useEffect(() => {
        if (skipExternalSync.current) {
            skipExternalSync.current = false
            return
        }

        const parsed = parseTemplateJson(value)
        if (!parsed) {
            setParseWarning(value.trim().length > 0)
            return
        }

        setParseWarning(false)
        setSections(parsed.sections)
        setEditingSectionIds(new Set())
    }, [value])

    const isSectionEditing = useCallback(
        (sectionId: string) => editingSectionIds.has(sectionId),
        [editingSectionIds],
    )

    const startEditing = useCallback((sectionId: string) => {
        setEditingSectionIds((previous) => {
            const next = new Set(previous)
            next.add(sectionId)
            return next
        })
    }, [])

    const stopEditing = useCallback((sectionId: string) => {
        setEditingSectionIds((previous) => {
            const next = new Set(previous)
            next.delete(sectionId)
            return next
        })
    }, [])

    const markNewSectionEditing = useCallback(
        (nextSections: TemplateSection[], parentPath: SectionPath) => {
            const newSectionId = getLastAddedChildId(nextSections, parentPath)
            if (!newSectionId) {
                return
            }

            setEditingSectionIds((previous) => {
                const next = new Set(previous)
                next.add(newSectionId)
                return next
            })
        },
        [],
    )

    const publish = (nextSections: TemplateSection[]) => {
        setSections(nextSections)
        skipExternalSync.current = true
        onChange(serializeTemplateContent({ sections: nextSections }))
    }

    const handleUpdate = (path: SectionPath, patch: Partial<TemplateSection>) => {
        publish(updateSectionAtPath(sections, path, patch))
    }

    const handleRemove = (path: SectionPath) => {
        const section = getSectionAtPath(sections, path)
        const nextSections = removeSectionAtPath(sections, path)
        publish(nextSections)

        if (!section) {
            return
        }

        setEditingSectionIds((previous) => {
            const next = new Set(previous)
            next.delete(section.id)
            return next
        })
    }

    const handleAddChild = (parentPath: SectionPath) => {
        const nextSections = addChildSectionAtPath(sections, parentPath)
        publish(nextSections)
        markNewSectionEditing(nextSections, parentPath)
    }

    const handleAddRootSection = () => {
        handleAddChild([])
    }

    return (
        <div className={styles.root}>
            {parseWarning ? (
                <div className={styles.parseWarning}>
                    Uploaded JSON could not be loaded into the editor. Fix the file or edit the
                    structure below; saving will overwrite the previous JSON.
                </div>
            ) : null}

            <div className={styles.content}>
                {sections.length === 0 ? (
                    <div className={styles.emptyState}>
                        No sections yet. Add a section to get started.
                    </div>
                ) : (
                    <ul className={styles.sectionList}>
                        {sections.map((section, sectionIndex) => (
                            <SectionNodeEditor
                                key={section.id}
                                section={section}
                                path={[sectionIndex]}
                                depth={0}
                                isEditing={isSectionEditing(section.id)}
                                isSectionEditing={isSectionEditing}
                                onUpdate={handleUpdate}
                                onRemove={handleRemove}
                                onAddChild={handleAddChild}
                                onStartEditing={startEditing}
                                onStopEditing={stopEditing}
                            />
                        ))}
                    </ul>
                )}
            </div>

            <button
                type="button"
                className="btn btn-outline-secondary with-icon"
                onClick={handleAddRootSection}
            >
                <i className="fas fa-plus" aria-hidden="true" />
                Add section
            </button>
        </div>
    )
}
