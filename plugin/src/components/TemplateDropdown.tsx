import { Icon, Spinner } from '@ds-wizard/plugin-sdk/ui/Icon'
import { type KeyboardEvent, useEffect, useId, useRef, useState } from 'react'

import styles from '@/components/TemplateDropdown.module.css'
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

/** Template selection and creation in one menu, grouped by ownership. */
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
    const [isOpen, setIsOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)
    const toggleRef = useRef<HTMLButtonElement>(null)
    const menuRef = useRef<HTMLDivElement>(null)
    const openFromEnd = useRef(false)
    const id = useId()
    const menuOpen = isOpen && !isLoading && !disabled
    const selectedTemplate = templates.find((template) => template.uuid === value)
    const displayLabel = isLoading ? loadingLabel : (selectedTemplate?.title ?? placeholder)
    const groups = [
        { label: 'My templates', icon: 'fa-user', scope: 'personal' },
        { label: 'Common templates', icon: 'fa-building', scope: 'tenant' },
    ]

    const closeMenu = () => {
        setIsOpen(false)
        toggleRef.current?.focus()
    }

    useEffect(() => {
        if (!menuOpen) return

        const items = menuRef.current?.querySelectorAll<HTMLButtonElement>('[role^="menuitem"]')
        const selected = menuRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')
        const initial = openFromEnd.current ? items?.[items.length - 1] : (selected ?? items?.[0])
        initial?.focus()

        const handlePointerDown = (event: PointerEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false)
        }
        document.addEventListener('pointerdown', handlePointerDown)
        return () => document.removeEventListener('pointerdown', handlePointerDown)
    }, [menuOpen])

    const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            closeMenu()
            return
        }
        if (event.key === 'Tab') {
            // Return to the trigger before the browser advances to the next control.
            closeMenu()
            return
        }
        const items = Array.from(
            menuRef.current?.querySelectorAll<HTMLButtonElement>('[role^="menuitem"]') ?? [],
        )
        if (!items.length) return
        const index = items.indexOf(document.activeElement as HTMLButtonElement)
        let nextIndex: number
        switch (event.key) {
            case 'ArrowDown':
                nextIndex = (index + 1) % items.length
                break
            case 'ArrowUp':
                nextIndex = (index - 1 + items.length) % items.length
                break
            case 'Home':
                nextIndex = 0
                break
            case 'End':
                nextIndex = items.length - 1
                break
            default:
                return
        }
        event.preventDefault()
        items[nextIndex].focus()
    }

    return (
        <div
            className={styles.root}
            ref={rootRef}
            onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) setIsOpen(false)
            }}
        >
            <label className="ui-field__label" htmlFor={`${id}-toggle`}>
                {label}
            </label>
            <button
                ref={toggleRef}
                id={`${id}-toggle`}
                type="button"
                className={`ui-input ${styles.toggle}`}
                disabled={isLoading || disabled}
                aria-busy={isLoading}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-controls={menuOpen ? `${id}-menu` : undefined}
                onClick={() => {
                    openFromEnd.current = false
                    setIsOpen((current) => !current)
                }}
                onKeyDown={(event) => {
                    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                        event.preventDefault()
                        openFromEnd.current = event.key === 'ArrowUp'
                        setIsOpen(true)
                    }
                }}
            >
                <span className={styles.toggleLabel}>{displayLabel}</span>
                <span className={styles.caret} aria-hidden="true">
                    {isLoading ? <Spinner /> : <Icon name="fa-chevron-down" />}
                </span>
            </button>

            {menuOpen && (
                <div
                    ref={menuRef}
                    id={`${id}-menu`}
                    className={styles.menu}
                    role="menu"
                    aria-label={label}
                    onKeyDown={handleMenuKeyDown}
                >
                    {groups.map((group) => {
                        const options = templates.filter(
                            (template) => template.scope === group.scope,
                        )
                        if (!options.length) return null
                        return (
                            <div key={group.scope} role="group" aria-label={group.label}>
                                <div className={styles.groupLabel} aria-hidden="true">
                                    <Icon name={group.icon} />
                                    {group.label}
                                </div>
                                {options.map((template) => (
                                    <button
                                        key={template.uuid}
                                        type="button"
                                        role="menuitemradio"
                                        tabIndex={-1}
                                        aria-checked={value === template.uuid}
                                        className={`${styles.item} ${value === template.uuid ? styles.itemActive : ''}`}
                                        onClick={() => {
                                            onChange(template.uuid)
                                            closeMenu()
                                        }}
                                    >
                                        {template.title}
                                    </button>
                                ))}
                            </div>
                        )
                    })}
                    {!templates.length && (
                        <div className={styles.emptyState}>No templates available yet.</div>
                    )}
                    {onCreate && (
                        <button
                            type="button"
                            role="menuitem"
                            tabIndex={-1}
                            className={`${styles.item} ${styles.createItem}`}
                            onClick={() => {
                                closeMenu()
                                onCreate()
                            }}
                        >
                            <Icon name="fa-plus" />
                            Create your own template
                        </button>
                    )}
                </div>
            )}
        </div>
    )
}
