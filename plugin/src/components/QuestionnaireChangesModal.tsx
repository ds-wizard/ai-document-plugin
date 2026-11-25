import { Alert } from '@ds-wizard/plugin-sdk/ui/Alert'
import { AsyncBlock } from '@ds-wizard/plugin-sdk/ui/AsyncBlock'
import { Muted, VisuallyHidden } from '@ds-wizard/plugin-sdk/ui/Text'
import { useEffect, useRef, useState } from 'react'

import { getQuestionnaireChanges } from '@/client'
import { Modal } from '@/components/Modal'
import styles from '@/components/QuestionnaireChangesModal.module.css'
import type {
    QuestionnaireChangeNode,
    QuestionnaireChangesResponse,
    QuestionnaireValueChange,
} from '@/types'

type QuestionnaireChangesModalProps = {
    runId: string
    onClose: () => void
}

type LoadState =
    | { status: 'loading' }
    | { status: 'failed'; message: string }
    | { status: 'ready'; data: QuestionnaireChangesResponse }

const UNTITLED: Record<QuestionnaireChangeNode['kind'], string> = {
    chapter: 'Untitled chapter',
    question: 'Unknown question',
    item: 'Untitled item',
}

// Long answers are cut so a line of the tree stays short; the whole value is shown on hover.
const MAX_VALUE_LENGTH = 200

function shorten(value: string): string {
    return value.length > MAX_VALUE_LENGTH ? `${value.slice(0, MAX_VALUE_LENGTH - 1)}…` : value
}

/** The old value struck through in red and the current one in green, either left out when there is none. */
function ChangeValues({ change }: { change: QuestionnaireValueChange }) {
    return (
        <span className={styles.values}>
            {change.oldValue && (
                <del className={styles.removed} title={change.oldValue}>
                    <VisuallyHidden>Removed: </VisuallyHidden>
                    {shorten(change.oldValue)}
                </del>
            )}
            {change.newValue && (
                <ins className={styles.added} title={change.newValue}>
                    <VisuallyHidden>Added: </VisuallyHidden>
                    {shorten(change.newValue)}
                </ins>
            )}
        </span>
    )
}

function TreeNode({ node }: { node: QuestionnaireChangeNode }) {
    return (
        <li className={styles.node}>
            <div className={styles.line}>
                <span className={styles[node.kind]}>{node.title ?? UNTITLED[node.kind]}</span>
                {node.change ? (
                    <ChangeValues change={node.change} />
                ) : (
                    node.answer && (
                        <span className={styles.answer}>
                            <VisuallyHidden>Answer: </VisuallyHidden>
                            {node.answer}
                        </span>
                    )
                )}
            </div>
            {node.children.length > 0 && <TreeLevel nodes={node.children} />}
        </li>
    )
}

function TreeLevel({
    nodes,
    root = false,
}: {
    nodes: QuestionnaireChangeNode[]
    root?: boolean
}) {
    return (
        <ul className={root ? styles.root : styles.level}>
            {nodes.map((node) => (
                <TreeNode key={node.path} node={node} />
            ))}
        </ul>
    )
}

function ChangeTree({ tree }: { tree: QuestionnaireChangeNode[] }) {
    return (
        <div className={styles.tree}>
            <TreeLevel nodes={tree} root />
        </div>
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
    if (data.tree.length === 0) {
        return (
            <Muted>
                No answers differ from when this document was generated. Only other parts of the
                questionnaire, such as its phase or labels, were edited.
            </Muted>
        )
    }

    return <ChangeTree tree={data.tree} />
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
            fullHeight
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
