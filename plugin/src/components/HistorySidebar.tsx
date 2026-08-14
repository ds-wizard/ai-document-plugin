import {
    type PointerEvent as ReactPointerEvent,
    useCallback,
    useEffect,
    useRef,
    useState,
} from 'react'

import styles from '@/components/HistorySidebar.module.css'
import type { RunRecord, UseGenerationHistoryResult } from '@/hooks/useGenerationHistory'

type HistorySidebarProps = {
    history: UseGenerationHistoryResult
    selectedRunId: string | null
    onSelectNew: () => void
    onSelectRun: (runId: string) => void
}

const STATUS_ICON: Record<RunRecord['status'], string> = {
    queued: 'fas fa-spinner fa-spin',
    running: 'fas fa-spinner fa-spin',
    succeeded: 'fas fa-check-circle',
    failed: 'fas fa-exclamation-circle',
}

const RELATIVE_TIME_DIVISIONS: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
]

const relativeTimeFormatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

const MIN_THUMB_HEIGHT = 24

type ScrollThumb = { top: number; height: number }

const formatRelativeTime = (isoString: string): string => {
    const date = new Date(isoString)
    if (Number.isNaN(date.getTime())) {
        return ''
    }

    const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000)

    for (const [unit, secondsInUnit] of RELATIVE_TIME_DIVISIONS) {
        if (Math.abs(diffSeconds) >= secondsInUnit) {
            return relativeTimeFormatter.format(Math.round(diffSeconds / secondsInUnit), unit)
        }
    }

    return 'a few seconds ago'
}

export function HistorySidebar({
    history,
    selectedRunId,
    onSelectNew,
    onSelectRun,
}: HistorySidebarProps) {
    const { items, isLoading } = history
    const activeItemRef = useRef<HTMLButtonElement | null>(null)
    const listRef = useRef<HTMLDivElement | null>(null)
    const [thumb, setThumb] = useState<ScrollThumb | null>(null)

    // The native scrollbar is hidden (it would sit on the divider), so the
    // overlay thumb below is measured from the list instead.
    const updateThumb = useCallback(() => {
        const list = listRef.current
        if (!list) {
            return
        }

        const { scrollTop, scrollHeight, clientHeight } = list
        if (scrollHeight - clientHeight < 1) {
            setThumb(null)
            return
        }

        const height = Math.max((clientHeight / scrollHeight) * clientHeight, MIN_THUMB_HEIGHT)
        const top =
            (scrollTop / (scrollHeight - clientHeight)) * (clientHeight - height) + list.offsetTop
        setThumb({ top, height })
    }, [])

    useEffect(() => {
        updateThumb()
    }, [updateThumb, items.length])

    useEffect(() => {
        const list = listRef.current
        if (!list) {
            return
        }

        const observer = new ResizeObserver(updateThumb)
        observer.observe(list)
        return () => observer.disconnect()
    }, [updateThumb])

    // The selected run can be off-screen after a new run starts or the list loads.
    useEffect(() => {
        activeItemRef.current?.scrollIntoView({ block: 'nearest' })
    }, [selectedRunId, items.length])

    const handleThumbPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
        const list = listRef.current
        if (!list || !thumb) {
            return
        }

        event.preventDefault()
        const startY = event.clientY
        const startScrollTop = list.scrollTop
        const trackRange = list.clientHeight - thumb.height
        const scrollRange = list.scrollHeight - list.clientHeight

        const handleMove = (moveEvent: PointerEvent) => {
            const ratio = trackRange > 0 ? (moveEvent.clientY - startY) / trackRange : 0
            list.scrollTop = startScrollTop + ratio * scrollRange
        }

        const handleUp = () => {
            window.removeEventListener('pointermove', handleMove)
            window.removeEventListener('pointerup', handleUp)
        }

        window.addEventListener('pointermove', handleMove)
        window.addEventListener('pointerup', handleUp)
    }

    return (
        <nav className={styles.root} aria-label="Generation history">
            <button
                type="button"
                onClick={onSelectNew}
                disabled={selectedRunId === null}
                className={`${styles.newButton} ${selectedRunId === null ? styles.itemActive : ''}`}
            >
                <i className={`fas fa-plus ${styles.statusIcon}`} aria-hidden="true" />
                Generate new DMP
            </button>

            <div className={styles.list} role="list" ref={listRef} onScroll={updateThumb}>
                {items.map((item) => (
                    <button
                        key={item.runId}
                        ref={selectedRunId === item.runId ? activeItemRef : null}
                        type="button"
                        role="listitem"
                        onClick={() => onSelectRun(item.runId)}
                        className={`${styles.item} ${selectedRunId === item.runId ? styles.itemActive : ''}`}
                    >
                        <i
                            className={`${STATUS_ICON[item.status]} ${styles.statusIcon} ${styles[item.status]}`}
                            aria-hidden="true"
                        />
                        <span className={styles.itemBody}>
                            <span className={styles.itemTitle}>{item.templateTitle}</span>
                            <span className={styles.itemTime}>
                                {formatRelativeTime(item.createdAt)}
                            </span>
                        </span>
                    </button>
                ))}

                {items.length === 0 && !isLoading ? (
                    <div className={styles.emptyState}>No generations yet.</div>
                ) : null}
            </div>

            {thumb ? (
                <div
                    className={styles.scrollThumb}
                    style={{ top: thumb.top, height: thumb.height }}
                    onPointerDown={handleThumbPointerDown}
                    aria-hidden="true"
                />
            ) : null}
        </nav>
    )
}
