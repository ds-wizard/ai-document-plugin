export type TemplateSection = {
    id: string
    title: string
    description: string
    sections: TemplateSection[]
}

export type TemplateContent = {
    sections: TemplateSection[]
}

export type SectionPath = number[]

export function createSection(): TemplateSection {
    return {
        id: crypto.randomUUID(),
        title: '',
        description: '',
        sections: [],
    }
}

export function serializeTemplateContent(content: TemplateContent): string {
    return JSON.stringify(
        {
            sections: content.sections.map(serializeSectionNode),
        },
        null,
        2,
    )
}

function serializeSectionNode(section: TemplateSection): Record<string, unknown> {
    const entry: Record<string, unknown> = {
        title: section.title.trim() || 'Untitled section',
    }
    if (section.description.trim()) {
        entry.content = section.description.trim()
    }
    if (section.sections.length > 0) {
        entry.sections = section.sections.map(serializeSectionNode)
    }
    return entry
}

export function parseTemplateJson(json: string): TemplateContent | null {
    const trimmed = json.trim()
    if (!trimmed) {
        return { sections: [] }
    }

    try {
        const parsed = JSON.parse(trimmed) as { sections?: unknown }
        if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sections)) {
            return null
        }

        return {
            sections: parsed.sections
                .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
                .map(parseSectionNode),
        }
    } catch {
        return null
    }
}

function parseSectionNode(node: Record<string, unknown>): TemplateSection {
    const nested = node.sections
    const childSections = Array.isArray(nested)
        ? nested
              .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
              .map(parseSectionNode)
        : []

    return {
        id: crypto.randomUUID(),
        title: typeof node.title === 'string' ? node.title : '',
        description: typeof node.content === 'string' ? node.content : '',
        sections: childSections,
    }
}

export function updateSectionAtPath(
    sections: TemplateSection[],
    path: SectionPath,
    patch: Partial<TemplateSection>,
): TemplateSection[] {
    if (path.length === 0) {
        return sections
    }

    const [index, ...rest] = path
    return sections.map((section, sectionIndex) => {
        if (sectionIndex !== index) {
            return section
        }

        if (rest.length === 0) {
            return { ...section, ...patch }
        }

        return {
            ...section,
            sections: updateSectionAtPath(section.sections, rest, patch),
        }
    })
}

export function addChildSectionAtPath(
    sections: TemplateSection[],
    parentPath: SectionPath,
): TemplateSection[] {
    if (parentPath.length === 0) {
        return [...sections, createSection()]
    }

    const [index, ...rest] = parentPath
    return sections.map((section, sectionIndex) => {
        if (sectionIndex !== index) {
            return section
        }

        if (rest.length === 0) {
            return {
                ...section,
                sections: [...section.sections, createSection()],
            }
        }

        return {
            ...section,
            sections: addChildSectionAtPath(section.sections, rest),
        }
    })
}

export function getSectionAtPath(
    sections: TemplateSection[],
    path: SectionPath,
): TemplateSection | null {
    if (path.length === 0) {
        return null
    }

    let currentList = sections
    let current: TemplateSection | undefined

    for (const index of path) {
        current = currentList[index]
        if (!current) {
            return null
        }
        currentList = current.sections
    }

    return current ?? null
}

export function getLastAddedChildId(
    sections: TemplateSection[],
    parentPath: SectionPath,
): string | null {
    if (parentPath.length === 0) {
        return sections[sections.length - 1]?.id ?? null
    }

    const parent = getSectionAtPath(sections, parentPath)
    const children = parent?.sections
    return children?.[children.length - 1]?.id ?? null
}

export function removeSectionAtPath(
    sections: TemplateSection[],
    path: SectionPath,
): TemplateSection[] {
    if (path.length === 0) {
        return sections
    }

    const [index, ...rest] = path
    if (rest.length === 0) {
        return sections.filter((_, sectionIndex) => sectionIndex !== index)
    }

    return sections.map((section, sectionIndex) => {
        if (sectionIndex !== index) {
            return section
        }

        return {
            ...section,
            sections: removeSectionAtPath(section.sections, rest),
        }
    })
}
