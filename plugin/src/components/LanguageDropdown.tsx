import { useDeferredValue, useEffect, useId, useRef, useState } from 'react'

import styles from '@/components/LanguageDropdown.module.css'
import { filterLanguageOptions, getLanguageOption } from '@/data/languages'

type LanguageDropdownProps = {
    value: string
    onChange: (value: string) => void
    disabled?: boolean
    label?: string
    placeholder?: string
    searchPlaceholder?: string
}

const capitalizeLabel = (label: string): string =>
    label ? label[0].toLocaleUpperCase() + label.slice(1) : label

export function LanguageDropdown({
    value,
    onChange,
    disabled = false,
    label = 'Language',
    placeholder = 'Select language',
    searchPlaceholder = 'Search language...',
}: LanguageDropdownProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [query, setQuery] = useState('')
    const deferredQuery = useDeferredValue(query)
    const rootRef = useRef<HTMLDivElement | null>(null)
    const searchInputRef = useRef<HTMLInputElement | null>(null)
    const listboxId = useId()

    const selectedOption = getLanguageOption(value)
    const visibleOptions = filterLanguageOptions(deferredQuery)
    const displayLabel = selectedOption ? capitalizeLabel(selectedOption.nativeLabel) : placeholder

    useEffect(() => {
        if (!isOpen) {
            return
        }

        searchInputRef.current?.focus()

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
        setQuery('')
    }

    return (
        <label className={styles.field}>
            <span className={styles.label}>{label}</span>

            <div className={styles.root} ref={rootRef}>
                <button
                    type="button"
                    disabled={disabled}
                    className={styles.toggle}
                    onClick={() => {
                        setIsOpen((currentValue) => !currentValue)
                        setQuery('')
                    }}
                    aria-expanded={isOpen}
                    aria-haspopup="listbox"
                    aria-controls={listboxId}
                >
                    <span className={styles.toggleLabel}>{displayLabel}</span>
                    <span className={styles.caret} aria-hidden="true">
                        ▼
                    </span>
                </button>

                {isOpen ? (
                    <div className={styles.menu}>
                        <div className={styles.searchWrap}>
                            <input
                                ref={searchInputRef}
                                type="search"
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                placeholder={searchPlaceholder}
                                className={styles.searchInput}
                            />
                        </div>

                        <div id={listboxId} className={styles.list} role="listbox">
                            {visibleOptions.length > 0 ? (
                                visibleOptions.map((option) => (
                                    <button
                                        key={option.code}
                                        type="button"
                                        role="option"
                                        aria-selected={value === option.code}
                                        className={`${styles.item} ${
                                            value === option.code ? styles.itemActive : ''
                                        }`}
                                        onClick={() => handleSelect(option.code)}
                                    >
                                        <span className={styles.itemPrimary}>
                                            {capitalizeLabel(option.nativeLabel)}
                                        </span>
                                        <span className={styles.itemMeta}>
                                            {capitalizeLabel(option.englishLabel)}
                                        </span>
                                    </button>
                                ))
                            ) : (
                                <div className={styles.emptyState}>
                                    No languages match “{query.trim()}”.
                                </div>
                            )}
                        </div>
                    </div>
                ) : null}
            </div>
        </label>
    )
}
