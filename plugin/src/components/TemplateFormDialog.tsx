import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { CheckboxField, TextField } from '@ds-wizard/plugin-sdk/ui/Field'
import { FileUpload } from '@ds-wizard/plugin-sdk/ui/FileUpload'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Separator } from '@ds-wizard/plugin-sdk/ui/Separator'
import { Muted, Subtitle } from '@ds-wizard/plugin-sdk/ui/Text'
import { token } from '@ds-wizard/plugin-sdk/ui/tokens'
import { type CSSProperties, useState } from 'react'
import { toast } from 'sonner'

import { createTemplate, updateTemplate } from '@/client'
import { CoverPagePreview } from '@/components/CoverPagePreview'
import { Modal } from '@/components/Modal'
import { TemplateStructureEditor } from '@/components/TemplateStructureEditor'
import type { ApiTemplateContent, TemplateDetail, TemplateOption, TemplateScope } from '@/types'

/** What the form works on: an existing template to edit, or `'new'` to create one. */
export type TemplateFormTarget = TemplateDetail | 'new'

type TemplateFormDialogProps = {
    language?: string
    scope: TemplateScope
    target: TemplateFormTarget
    onSaved: (template: TemplateOption) => void
    onClose: () => void
}

type InputMode = 'visual' | 'file'

const INPUT_MODES: { mode: InputMode; label: string }[] = [
    { mode: 'visual', label: 'Visual editor' },
    { mode: 'file', label: 'From file' },
]

const scopeNoun = (scope: TemplateScope): string =>
    scope === 'tenant' ? 'tenant-wide template' : 'personal template'

const parseTemplateContent = (json: string): ApiTemplateContent => {
    const parsed = JSON.parse(json) as { sections?: unknown } | null
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.sections)) {
        throw new Error('Template JSON must contain a top-level "sections" array.')
    }
    return parsed as ApiTemplateContent
}

/**
 * Dialog with the form for creating or editing a template.
 *
 * Mount it to open it: the form starts from `target` each time, so nothing has to be reset.
 */
export function TemplateFormDialog({
    scope,
    target,
    onSaved,
    onClose,
    language = 'en',
}: TemplateFormDialogProps) {
    const editedTemplate = target === 'new' ? null : target
    const [hasCoverPage, setHasCoverPage] = useState(editedTemplate?.hasCoverPage ?? false)
    const [title, setTitle] = useState(editedTemplate?.title ?? '')
    const [json, setJson] = useState(
        editedTemplate ? JSON.stringify(editedTemplate.content, null, 2) : '',
    )
    const [file, setFile] = useState<File | null>(null)
    const [isSaving, setIsSaving] = useState(false)
    const [inputMode, setInputMode] = useState<InputMode>('visual')

    const processTemplateFile = async (nextFile: File) => {
        try {
            const content = await nextFile.text()
            setFile(nextFile)
            setJson(content)
            if (!title.trim()) {
                setTitle(nextFile.name.replace(/\.json$/i, ''))
            }
            setInputMode('visual')
        } catch {
            toast.error('Failed to read the selected JSON file.')
        }
    }

    const handleSave = async () => {
        const trimmedTitle = title.trim()
        const trimmedJson = json.trim()

        if (!trimmedTitle) {
            toast.error('Enter a template title.')
            return
        }

        if (!trimmedJson) {
            toast.error('Insert or upload template JSON.')
            return
        }

        try {
            const template = {
                title: trimmedTitle,
                content: parseTemplateContent(trimmedJson),
                hasCoverPage,
            }

            setIsSaving(true)
            const saved = editedTemplate
                ? await updateTemplate({ ...template, uuid: editedTemplate.uuid })
                : await createTemplate({ ...template, scope })

            onSaved(saved)
        } catch (saveError) {
            toast.error(
                saveError instanceof Error ? saveError.message : 'Template JSON is not valid.',
            )
        } finally {
            setIsSaving(false)
        }
    }

    const noun = scopeNoun(scope)
    const saveLabel = editedTemplate ? 'Update template' : 'Save template'
    const savingLabel = editedTemplate ? 'Updating template...' : 'Saving template...'

    return (
        <Modal
            open
            title={editedTemplate ? `Edit ${noun}` : `Create ${noun}`}
            onClose={onClose}
            closeDisabled={isSaving}
            footer={
                <>
                    <Button variant="ghost" onClick={onClose} disabled={isSaving}>
                        Cancel
                    </Button>
                    <Button variant="primary" loading={isSaving} onClick={() => void handleSave()}>
                        {isSaving ? savingLabel : saveLabel}
                    </Button>
                </>
            }
        >
            <Stack style={{ '--ui-stack-gap': token('--ui-space-3') } as CSSProperties}>
                <Stack>
                    <Subtitle>Template details</Subtitle>
                    <TextField
                        label="Template title"
                        value={title}
                        onChange={setTitle}
                        placeholder="My custom DMP template"
                    />
                </Stack>

                <Separator />

                <Stack>
                    <Stack style={{ gap: token('--ui-space-1') }}>
                        <Subtitle>Cover page</Subtitle>
                        <Muted>
                            Add DMP metadata and project information before your sections.
                        </Muted>
                    </Stack>
                    <CheckboxField
                        label="Include a cover page"
                        checked={hasCoverPage}
                        onChange={setHasCoverPage}
                        disabled={isSaving}
                    />
                    <CoverPagePreview key={language} language={language} />
                </Stack>

                <Separator />

                <Stack>
                    <Stack style={{ gap: token('--ui-space-1') }}>
                        <Subtitle>Template structure</Subtitle>
                        <Muted>
                            Build your document’s sections or import an existing template.
                        </Muted>
                    </Stack>
                    <div role="group" aria-label="Template structure">
                        <Inline>
                            {INPUT_MODES.map(({ mode, label }) => (
                                <Button
                                    key={mode}
                                    size="small"
                                    pressed={inputMode === mode}
                                    onClick={() => setInputMode(mode)}
                                >
                                    {label}
                                </Button>
                            ))}
                        </Inline>
                    </div>

                    {inputMode === 'visual' ? (
                        <TemplateStructureEditor value={json} onChange={setJson} />
                    ) : (
                        <FileUpload
                            label="Template JSON file"
                            accept=".json,application/json"
                            file={file}
                            onChange={(nextFile) => void processTemplateFile(nextFile)}
                            onClear={() => setFile(null)}
                            buttonLabel="Choose a JSON template"
                            hint="or drop it here"
                        />
                    )}
                </Stack>
            </Stack>
        </Modal>
    )
}
