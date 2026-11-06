import { Button } from '@ds-wizard/plugin-sdk/ui/Button'
import { Icon } from '@ds-wizard/plugin-sdk/ui/Icon'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { exportPipelineResultAsDocx } from '@/client'
import styles from '@/components/DownloadDropdown.module.css'
import { triggerBlobDownload } from '@/download'

type DownloadDropdownProps = {
    markdown: string
    runId: string | null
    baseName: string
}

/**
 * Download menu for a pipeline result, offering the raw markdown or a Word export.
 *
 * The markdown passed in is the editor's current text, so unsaved edits are downloaded too.
 */
export function DownloadDropdown({ markdown, runId, baseName }: DownloadDropdownProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [isDownloadingDocx, setIsDownloadingDocx] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)

    const fileBaseName = baseName || 'pipeline-output'

    useEffect(() => {
        if (!isOpen) {
            return
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handlePointerDown)
        document.addEventListener('keydown', handleEscape)

        return () => {
            document.removeEventListener('mousedown', handlePointerDown)
            document.removeEventListener('keydown', handleEscape)
        }
    }, [isOpen])

    const onDownloadMarkdown = () => {
        setIsOpen(false)

        if (!markdown) {
            return
        }

        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
        triggerBlobDownload(blob, `${fileBaseName}.md`)
        toast.success('Markdown download has started.')
    }

    const onDownloadDocx = async () => {
        setIsOpen(false)

        if (!markdown || !runId) {
            toast.error('There is no pipeline result to export yet.')
            return
        }

        setIsDownloadingDocx(true)
        try {
            const blob = await exportPipelineResultAsDocx(runId, markdown)
            triggerBlobDownload(blob, `${fileBaseName}.docx`)
            toast.success('Word download has started.')
        } catch (error) {
            toast.error(
                error instanceof Error
                    ? error.message
                    : 'Failed to export the result as a Word document.',
            )
        } finally {
            setIsDownloadingDocx(false)
        }
    }

    return (
        <div className={styles.root} ref={rootRef}>
            <Button
                icon="fa-download"
                loading={isDownloadingDocx}
                onClick={() => setIsOpen((currentValue) => !currentValue)}
                aria-expanded={isOpen}
                aria-haspopup="menu"
            >
                {isDownloadingDocx ? 'Preparing...' : 'Download'}
                <span className={styles.caret}>
                    <Icon name="fa-chevron-down" />
                </span>
            </Button>

            {isOpen ? (
                <div className={styles.menu} role="menu">
                    <button
                        type="button"
                        role="menuitem"
                        onClick={onDownloadMarkdown}
                        className={styles.item}
                    >
                        <Icon name="far fa-file-lines" className={styles.itemIcon} />
                        Markdown
                    </button>

                    <button
                        type="button"
                        role="menuitem"
                        onClick={() => void onDownloadDocx()}
                        disabled={!runId}
                        className={styles.item}
                    >
                        <Icon name="far fa-file-word" className={styles.itemIcon} />
                        MS Word
                    </button>
                </div>
            ) : null}
        </div>
    )
}
