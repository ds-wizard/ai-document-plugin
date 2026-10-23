import { useId, useRef, useState } from 'react'

import styles from '@/components/DeleteRunModal.module.css'
import { Modal } from '@/components/Modal'
import { getRunTimeLabel, getRunVersionLabel, type RunRecord } from '@/hooks/useGenerationHistory'

type DeleteRunModalProps = {
    run: RunRecord
    onDelete: (runId: string) => Promise<void>
    onClose: () => void
}

export function DeleteRunModal({ run, onDelete, onClose }: DeleteRunModalProps) {
    const cancelRef = useRef<HTMLButtonElement>(null)
    const pendingRef = useRef(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const descriptionId = useId()

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
        <Modal
            open
            title="Delete this run?"
            descriptionId={descriptionId}
            busy={isDeleting}
            initialFocusRef={cancelRef}
            closeDisabled={isDeleting}
            onClose={() => {
                if (!pendingRef.current) onClose()
            }}
            footer={
                <>
                    <button
                        ref={cancelRef}
                        type="button"
                        className="btn btn-outline-secondary"
                        disabled={isDeleting}
                        onClick={() => {
                            if (!pendingRef.current) onClose()
                        }}
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
                </>
            }
        >
            <div className={styles.run}>
                <strong>{run.templateTitle}</strong>
                <span>
                    {getRunVersionLabel(run)} · {getRunTimeLabel(run)}
                </span>
            </div>
            <p id={descriptionId} className={styles.description}>
                This will permanently remove the run and its generated document from your history.
            </p>
        </Modal>
    )
}
