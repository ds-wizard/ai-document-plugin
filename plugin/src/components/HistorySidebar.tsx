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

export function HistorySidebar({ history, selectedRunId, onSelectNew, onSelectRun }: HistorySidebarProps) {
    const { items, isLoading } = history

    return (
        <nav className={styles.root} aria-label="Generation history">
            <button
                type="button"
                onClick={onSelectNew}
                className={`${styles.newButton} ${selectedRunId === null ? styles.itemActive : ''}`}
            >
                <i className="fas fa-plus" aria-hidden="true" />
                Generate new DMP
            </button>

            <div className={styles.list} role="list">
                {items.map((item) => (
                    <button
                        key={item.runId}
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
                            <span className={styles.itemTime}>{formatRelativeTime(item.createdAt)}</span>
                        </span>
                    </button>
                ))}

                {items.length === 0 && !isLoading ? (
                    <div className={styles.emptyState}>No generations yet.</div>
                ) : null}
            </div>
        </nav>
    )
}
