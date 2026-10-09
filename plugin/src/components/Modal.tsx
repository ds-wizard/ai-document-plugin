import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'

import styles from '@/components/Modal.module.css'

type ModalProps = {
    title: ReactNode
    onClose: () => void
    children: ReactNode
    footer?: ReactNode
    closeDisabled?: boolean
}

/**
 * Modal dialog that is open for as long as it is mounted.
 *
 * Clicking outside does not close it, so unsaved input is not lost by a stray click
 * (or by interacting with a toast shown above the dialog).
 */
export function Modal({ title, onClose, children, footer, closeDisabled = false }: ModalProps) {
    return (
        <Dialog.Root
            open
            onOpenChange={(open) => {
                if (!open) {
                    onClose()
                }
            }}
        >
            <Dialog.Portal>
                <Dialog.Overlay className={styles.overlay} />
                <Dialog.Content
                    className={styles.content}
                    aria-describedby={undefined}
                    onInteractOutside={(event) => event.preventDefault()}
                    onEscapeKeyDown={(event) => {
                        if (closeDisabled) {
                            event.preventDefault()
                        }
                    }}
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
