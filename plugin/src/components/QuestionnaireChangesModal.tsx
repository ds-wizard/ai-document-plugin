import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Badge, type BadgeProps } from '@ds-wizard/plugin-sdk/ui/Badge'
import { Icon } from '@ds-wizard/plugin-sdk/ui/Icon'
import { Muted } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect, useRef, useState } from 'react'

import { getQuestionnaireChanges } from '@/client'
import { Modal } from '@/components/Modal'
import styles from '@/components/QuestionnaireChangesModal.module.css'
import type { QuestionnaireChange, QuestionnaireChangesResponse } from '@/types'

type QuestionnaireChangesModalProps = {
    runId: string
    onClose: () => void
}

type LoadState =
    | { status: 'loading' }
    | { status: 'failed'; message: string }
    | { status: 'ready'; data: QuestionnaireChangesResponse }

const KIND_LABELS: Record<QuestionnaireChange['kind'], string> = {
    added: 'Added',
    changed: 'Changed',
    removed: 'Removed',
}

const KIND_TONES: Record<QuestionnaireChange['kind'], NonNullable<BadgeProps['tone']>> = {
    added: 'success',
    changed: 'info',
    removed: 'danger',
}

const OTHER_CHAPTER = 'Other'

function groupByChapter(changes: QuestionnaireChange[]): Array<[string, QuestionnaireChange[]]> {
    const groups = new Map<string, QuestionnaireChange[]>()
    for (const change of changes) {
        const chapter = change.chapterTitle ?? OTHER_CHAPTER
        groups.set(chapter, [...(groups.get(chapter) ?? []), change])
    }
    return [...groups]
}

function formatChangedAt(changedAt: string | null): string | null {
    if (!changedAt) return null
    const date = new Date(changedAt)
    return Number.isNaN(date.getTime()) ? null : date.toLocaleString()
}

function Value({ value, old = false }: { value: string | null; old?: boolean }) {
    if (!value) {
        return <span className={styles.empty}>(empty)</span>
    }
    return <span className={old ? `${styles.value} ${styles.old}` : styles.value}>{value}</span>
}

function ChangeValues({ change }: { change: QuestionnaireChange }) {
    if (change.kind === 'added') {
        return (
            <div className={styles.values}>
                <Value value={change.newValue} />
            </div>
        )
    }
    if (change.kind === 'removed') {
        return (
            <div className={styles.values}>
                <Value value={change.oldValue} old />
            </div>
        )
    }
    return (
        <div className={styles.values}>
            <Value value={change.oldValue} old />
            <Icon name="fa-arrow-right" />
            <Value value={change.newValue} />
        </div>
    )
}

function ChangeItem({ change }: { change: QuestionnaireChange }) {
    const changedAt = formatChangedAt(change.changedAt)
    const meta = [change.changedBy, changedAt].filter(Boolean).join(', ')

    return (
        <li className={styles.change}>
            {change.context.length > 0 && (
                <div className={styles.context}>{change.context.join(' › ')}</div>
            )}
            <div className={styles.heading}>
                <Badge tone={KIND_TONES[change.kind]}>{KIND_LABELS[change.kind]}</Badge>
                <span>{change.questionTitle ?? 'Unknown question'}</span>
            </div>
            <ChangeValues change={change} />
            {meta && <div className={styles.meta}>{meta}</div>}
        </li>
    )
}

function ChangesContent({ data }: { data: QuestionnaireChangesResponse }) {
    if (!data.available) {
        return (
            <Alert tone="info">
                This document was generated before the answers were stored, so what changed cannot
                be shown.
            </Alert>
        )
    }
    if (data.changes.length === 0) {
        return (
            <Muted>
                No answers differ from when this document was generated. Only other parts of the
                questionnaire, such as its phase or labels, were edited.
            </Muted>
        )
    }

    return (
        <div className={styles.chapters}>
            {groupByChapter(data.changes).map(([chapter, changes]) => (
                <section key={chapter}>
                    <h3 className={styles.chapter}>{chapter}</h3>
                    <ul className={styles.list}>
                        {changes.map((change) => (
                            <ChangeItem key={change.path} change={change} />
                        ))}
                    </ul>
                </section>
            ))}
        </div>
    )
}

/** Lists the answers that differ between a generation and the questionnaire as it is now. */
export function QuestionnaireChangesModal({ runId, onClose }: QuestionnaireChangesModalProps) {
    const [state, setState] = useState<LoadState>({ status: 'loading' })
    const closeRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
        let cancelled = false
        setState({ status: 'loading' })
        void getQuestionnaireChanges(runId)
            .then((data) => {
                if (!cancelled) setState({ status: 'ready', data })
            })
            .catch((error: unknown) => {
                if (!cancelled) {
                    setState({
                        status: 'failed',
                        message:
                            error instanceof Error
                                ? error.message
                                : 'Failed to load the changes of the questionnaire.',
                    })
                }
            })

        return () => {
            cancelled = true
        }
    }, [runId])

    return (
        <Modal
            open
            title="Questionnaire changes since this document was generated"
            busy={state.status === 'loading'}
            initialFocusRef={closeRef}
            onClose={onClose}
            footer={
                <button
                    ref={closeRef}
                    type="button"
                    className="btn btn-outline-secondary"
                    onClick={onClose}
                >
                    Close
                </button>
            }
        >
            <AsyncBlock
                loading={state.status === 'loading'}
                loadingLabel="Loading changes..."
                error={state.status === 'failed' ? state.message : undefined}
            >
                {state.status === 'ready' && <ChangesContent data={state.data} />}
            </AsyncBlock>
        </Modal>
    )
}
