import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode, RefObject } from 'react'

import styles from '@/components/Modal.module.css'

type ModalProps = {
    open: boolean
    title: ReactNode
    onClose: () => void
    children: ReactNode
    footer?: ReactNode
    descriptionId?: string
    busy?: boolean
    initialFocusRef?: RefObject<HTMLElement | null>
    /** Blocks closing, e.g. while the content is being saved. */
    closeDisabled?: boolean
}

/**
 * Modal dialog with a title bar, scrollable body and optional footer.
 *
 * Clicking outside does not close it, so unsaved input is not lost by a stray click
 * (or by interacting with a toast shown above the dialog).
 */
export function Modal({
    open,
    title,
    onClose,
    children,
    footer,
    descriptionId,
    busy,
    initialFocusRef,
    closeDisabled = false,
}: ModalProps) {
    return (
        <Dialog.Root
            open={open}
            onOpenChange={(nextOpen) => !nextOpen && !closeDisabled && onClose()}
        >
            <Dialog.Portal>
                <Dialog.Overlay className={styles.overlay} />
                <Dialog.Content
                    className={styles.content}
                    aria-describedby={descriptionId}
                    aria-busy={busy}
                    onOpenAutoFocus={(event) => {
                        if (initialFocusRef?.current) {
                            event.preventDefault()
                            initialFocusRef.current.focus()
                        }
                    }}
                    onInteractOutside={(event) => event.preventDefault()}
                    onEscapeKeyDown={(event) => event.preventDefault()}
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
