import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { SelectField } from '@ds-wizard/plugin-sdk/ui/Field'
import { Inline, Stack } from '@ds-wizard/plugin-sdk/ui/Layout'

import type { TemplateOption } from '@/types'

type TemplateDropdownProps = {
    value: string
    onChange: (value: string) => void
    templates: TemplateOption[]
    onCreate?: () => void
    isLoading?: boolean
    disabled?: boolean
    label?: string
    placeholder?: string
    loadingLabel?: string
}

const toOption = (template: TemplateOption) => ({ value: template.uuid, label: template.title })

/** The template select, personal and tenant-wide templates grouped, with a button to create one. */
export function TemplateDropdown({
    value,
    onChange,
    templates,
    onCreate,
    isLoading = false,
    disabled = false,
    label = 'Template',
    placeholder = 'Select a template',
    loadingLabel = 'Loading templates...',
}: TemplateDropdownProps) {
    const personalTemplates = templates.filter((template) => template.scope === 'personal')
    const tenantTemplates = templates.filter((template) => template.scope === 'tenant')

    const groups = [
        { label: 'My templates', options: personalTemplates.map(toOption) },
        { label: 'Common templates', options: tenantTemplates.map(toOption) },
    ].filter((group) => group.options.length > 0)

    // A value that is no longer listed (e.g. just deleted) falls back to the placeholder.
    const selectedValue = templates.some((template) => template.uuid === value) ? value : ''

    return (
        <Stack>
            <SelectField
                label={label}
                value={selectedValue}
                onChange={onChange}
                options={[{ value: '', label: isLoading ? loadingLabel : placeholder }]}
                groups={groups}
                disabled={isLoading || disabled}
                hint={
                    !isLoading && templates.length === 0 ? 'No templates available yet.' : undefined
                }
            />

            {onCreate ? (
                <Inline>
                    <Button icon="fa-plus" disabled={disabled} onClick={onCreate}>
                        Create your own template
                    </Button>
                </Inline>
            ) : null}
        </Stack>
    )
}
