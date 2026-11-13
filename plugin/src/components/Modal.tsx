import { IconButton } from '@ds-wizard/plugin-sdk/ui/Button'
import { DialogBody, DialogFooter, DialogHeader } from '@ds-wizard/plugin-sdk/ui/Dialog'
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
 * Radix provides the mechanics (portal, focus trap, scroll lock); the wizard's dialog parts
 * draw the header, body and footer. The SDK's parts are made for the dialog the wizard opens
 * for an action, which a project tab or the settings page cannot open, hence Radix.
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
                    <DialogHeader
                        className={styles.fixed}
                        title={
                            <Dialog.Title asChild>
                                <span>{title}</span>
                            </Dialog.Title>
                        }
                        action={
                            <IconButton
                                icon="fa-xmark"
                                label="Close"
                                quiet
                                disabled={closeDisabled}
                                onClick={onClose}
                            />
                        }
                    />
                    <DialogBody className={styles.body}>{children}</DialogBody>
                    {footer ? <DialogFooter className={styles.fixed}>{footer}</DialogFooter> : null}
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    )
}
