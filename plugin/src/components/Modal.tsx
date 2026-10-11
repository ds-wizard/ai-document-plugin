import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'

import styles from '@/components/Modal.module.css'

type ModalProps = {
    open: boolean
    title: ReactNode
    onClose: () => void
    children: ReactNode
    footer?: ReactNode
    /** Blocks closing, e.g. while the content is being saved. */
    closeDisabled?: boolean
}

/**
 * Modal dialog with a title bar, scrollable body and optional footer.
 */
export function Modal({
    open,
    title,
    onClose,
    children,
    footer,
    closeDisabled = false,
}: ModalProps) {
    return (
        <Dialog.Root open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
            <Dialog.Portal>
                <Dialog.Overlay className={styles.overlay} />
                <Dialog.Content
                    className={styles.content}
                    aria-describedby={undefined}
                >
                    <div className={styles.header}>
                        <Dialog.Title className="ai-doc-title h5">{title}</Dialog.Title>
                        <Dialog.Close
                            className="btn-close"
                            aria-label="Close"
                            disabled={closeDisabled}
                        />
                    </div>
                    <div className={styles.body}>{children}</div>
                    {footer ? <div className={styles.footer}>{footer}</div> : null}
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    )
}
