import {
    type PointerEvent as ReactPointerEvent,
    useCallback,
    useEffect,
    useRef,
    useState,
} from 'react'

import { DeleteRunModal } from '@/components/DeleteRunModal'
import styles from '@/components/HistorySidebar.module.css'
import {
    getRunTimeLabel,
    getRunVersionLabel,
    type RunRecord,
    type UseGenerationHistoryResult,
} from '@/hooks/useGenerationHistory'

type HistorySidebarProps = {
    history: UseGenerationHistoryResult
    selectedRunId: string | null
    onSelectNew: () => void
    onDeleteRun: (runId: string) => Promise<void>
    onSelectRun: (runId: string) => void
}

const STATUS_ICON: Record<RunRecord['status'], string> = {
    queued: 'fas fa-spinner fa-spin',
    running: 'fas fa-spinner fa-spin',
    succeeded: 'fas fa-check-circle',
    failed: 'fas fa-exclamation-circle',
    cancelled: 'fas fa-ban',
}

const MIN_THUMB_HEIGHT = 24

type ScrollThumb = { top: number; height: number }

export function HistorySidebar({
    history,
    selectedRunId,
    onSelectNew,
    onDeleteRun,
    onSelectRun,
}: HistorySidebarProps) {
    const { items, isLoading } = history
    const activeItemRef = useRef<HTMLButtonElement | null>(null)
    const listRef = useRef<HTMLDivElement | null>(null)
    const [thumb, setThumb] = useState<ScrollThumb | null>(null)
    const [runToDelete, setRunToDelete] = useState<RunRecord | null>(null)

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
                    <div key={item.runId} role="listitem" className={styles.itemRow}>
                        <button
                            ref={selectedRunId === item.runId ? activeItemRef : null}
                            type="button"
                            onClick={() => onSelectRun(item.runId)}
                            className={`${styles.item} ${selectedRunId === item.runId ? styles.itemActive : ''} ${item.status !== 'queued' && item.status !== 'running' ? styles.itemWithClose : ''}`}
                        >
                            <span className={styles.statusSlot} aria-hidden="true">
                                {item.status !== 'queued' && item.status !== 'running' ? (
                                    <i
                                        className={`${STATUS_ICON[item.status]} ${styles.statusIcon} ${styles[item.status]}`}
                                    />
                                ) : null}
                            </span>
                            <span className={styles.itemBody}>
                                <span className={styles.itemTitle} title={item.templateTitle}>
                                    {item.templateTitle}
                                </span>
                                <span
                                    className={styles.itemVersion}
                                    title={getRunVersionLabel(item)}
                                >
                                    {getRunVersionLabel(item)}
                                </span>
                                <span className={styles.itemTime}>{getRunTimeLabel(item)}</span>
                            </span>
                        </button>
                        {item.status === 'queued' || item.status === 'running' ? (
                            <button
                                type="button"
                                className={styles.stopButton}
                                aria-label={
                                    history.cancellingRunIds.has(item.runId)
                                        ? 'Stopping pipeline'
                                        : 'Stop pipeline'
                                }
                                disabled={history.cancellingRunIds.has(item.runId)}
                                onClick={() => void history.cancelRun(item.runId)}
                            >
                                <span className={styles.stopRing} aria-hidden="true" />
                                <span className={styles.stopSquare} aria-hidden="true" />
                                <span className={styles.stopTooltip} aria-hidden="true">
                                    {history.cancellingRunIds.has(item.runId)
                                        ? 'Stopping pipeline…'
                                        : 'Stop pipeline'}
                                </span>
                            </button>
                        ) : (
                            <button
                                type="button"
                                className={styles.closeButton}
                                aria-label={
                                    history.deletingRunIds.has(item.runId)
                                        ? 'Deleting run'
                                        : 'Delete run'
                                }
                                disabled={history.deletingRunIds.has(item.runId)}
                                onClick={() => setRunToDelete(item)}
                            >
                                <i className="fas fa-times" aria-hidden="true" />
                                <span className={styles.closeTooltip} aria-hidden="true">
                                    {history.deletingRunIds.has(item.runId)
                                        ? 'Deleting run…'
                                        : 'Delete run'}
                                </span>
                            </button>
                        )}
                    </div>
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
            {runToDelete ? (
                <DeleteRunModal
                    run={runToDelete}
                    onDelete={onDeleteRun}
                    onClose={() => setRunToDelete(null)}
                />
            ) : null}
        </nav>
    )
}
