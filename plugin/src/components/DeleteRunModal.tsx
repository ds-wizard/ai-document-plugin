import { useEffect, useId, useRef, useState } from 'react'

import styles from '@/components/DeleteRunModal.module.css'
import { getRunTimeLabel, getRunVersionLabel, type RunRecord } from '@/hooks/useGenerationHistory'

type DeleteRunModalProps = {
    run: RunRecord
    onDelete: (runId: string) => Promise<void>
    onClose: () => void
}

export function DeleteRunModal({ run, onDelete, onClose }: DeleteRunModalProps) {
    const dialogRef = useRef<HTMLDialogElement>(null)
    const cancelRef = useRef<HTMLButtonElement>(null)
    const pendingRef = useRef(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const titleId = useId()
    const descriptionId = useId()

    useEffect(() => {
        const dialog = dialogRef.current
        // A modal dialog traps keyboard focus and makes the rest of the page inert.
        dialog?.showModal()
        cancelRef.current?.focus()
        return () => dialog?.close()
    }, [])

    const confirmDelete = async () => {
        if (pendingRef.current) return
        pendingRef.current = true
        setIsDeleting(true)
        try {
            await onDelete(run.runId)
        } finally {
            onClose()
        }
    }

    return (
        <dialog
            ref={dialogRef}
            className={styles.dialog}
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            aria-busy={isDeleting}
            onCancel={(event) => {
                event.preventDefault()
                if (!pendingRef.current) onClose()
            }}
        >
            <h3 id={titleId} className={styles.title}>
                Delete this run?
            </h3>
            <div className={styles.run}>
                <strong>{run.templateTitle}</strong>
                <span>
                    {getRunVersionLabel(run)} · {getRunTimeLabel(run)}
                </span>
            </div>
            <p id={descriptionId} className={styles.description}>
                This will permanently remove the run and its generated document from your history.
            </p>
            <div className={styles.actions}>
                <button
                    ref={cancelRef}
                    type="button"
                    className="btn btn-outline-secondary"
                    disabled={isDeleting}
                    onClick={onClose}
                >
                    Keep run
                </button>
                <button
                    type="button"
                    className="btn btn-danger"
                    disabled={isDeleting}
                    onClick={() => void confirmDelete()}
                >
                    {isDeleting ? 'Deleting…' : 'Delete run'}
                </button>
            </div>
        </dialog>
    )
}
