import { useEffect, useMemo, useRef, useState } from 'react'

import styles from '@/components/TemplateDropdown.module.css'
import type { TemplateOption } from '@/types'

export const CUSTOM_TEMPLATE_OPTION = '__custom_template__'

type TemplateDropdownProps = {
    value: string
    onChange: (value: string) => void
    templates: TemplateOption[]
    isLoading?: boolean
    disabled?: boolean
    placeholder?: string
    loadingLabel?: string
    customOptionLabel?: string
}

export function TemplateDropdown({
    value,
    onChange,
    templates,
    isLoading = false,
    disabled = false,
    placeholder = 'Select a template',
    loadingLabel = 'Loading templates...',
    customOptionLabel = 'Custom template...',
}: TemplateDropdownProps) {
    const [isOpen, setIsOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)

    const isCustomOption = value === CUSTOM_TEMPLATE_OPTION

    const displayLabel = useMemo(() => {
        if (!value) {
            return isLoading ? loadingLabel : placeholder
        }

        if (isCustomOption) {
            return customOptionLabel
        }

        const selectedTemplate = templates.find((template) => template.uuid === value)
        return selectedTemplate?.title ?? placeholder
    }, [customOptionLabel, isCustomOption, isLoading, loadingLabel, placeholder, templates, value])

    useEffect(() => {
        if (!isOpen) {
            return
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handlePointerDown)
        document.addEventListener('keydown', handleEscape)

        return () => {
            document.removeEventListener('mousedown', handlePointerDown)
            document.removeEventListener('keydown', handleEscape)
        }
    }, [isOpen])

    const handleSelect = (nextValue: string) => {
        onChange(nextValue)
        setIsOpen(false)
    }

    return (
        <div className={styles.root} ref={rootRef}>
            <button
                type="button"
                disabled={isLoading || disabled}
                className={styles.toggle}
                onClick={() => setIsOpen((currentValue) => !currentValue)}
                aria-expanded={isOpen}
                aria-haspopup="listbox"
            >
                <span>{displayLabel}</span>
                <span className={styles.caret} aria-hidden="true">
                    ▼
                </span>
            </button>

            {isOpen ? (
                <div className={styles.menu} role="listbox">
                    {templates.map((template) => (
                        <button
                            key={template.uuid}
                            type="button"
                            role="option"
                            aria-selected={value === template.uuid}
                            className={`${styles.item} ${
                                value === template.uuid ? styles.itemActive : ''
                            }`}
                            onClick={() => handleSelect(template.uuid)}
                        >
                            {template.title}
                        </button>
                    ))}

                    <button
                        type="button"
                        role="option"
                        aria-selected={isCustomOption}
                        className={`${styles.item} ${isCustomOption ? styles.itemActive : ''}`}
                        onClick={() => handleSelect(CUSTOM_TEMPLATE_OPTION)}
                    >
                        {customOptionLabel}
                    </button>
                </div>
            ) : null}
        </div>
    )
}
