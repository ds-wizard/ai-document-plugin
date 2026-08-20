import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { exportPipelineResultAsDocx } from '@/client'
import styles from '@/components/DownloadDropdown.module.css'

const triggerBlobDownload = (blob: Blob, fileName: string) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
}

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
            <button
                type="button"
                onClick={() => setIsOpen((currentValue) => !currentValue)}
                disabled={isDownloadingDocx}
                className="btn btn-outline-secondary"
                aria-expanded={isOpen}
                aria-haspopup="menu"
            >
                {isDownloadingDocx ? 'Preparing...' : 'Download'}
                <span className={styles.caret} aria-hidden="true">
                    ▼
                </span>
            </button>

            {isOpen ? (
                <div className={styles.menu} role="menu">
                    <button
                        type="button"
                        role="menuitem"
                        onClick={onDownloadMarkdown}
                        className={styles.item}
                    >
                        <i className={`fa far fa-file-alt ${styles.itemIcon}`} aria-hidden="true" />
                        Markdown
                    </button>

                    <button
                        type="button"
                        role="menuitem"
                        onClick={() => void onDownloadDocx()}
                        disabled={!runId}
                        className={styles.item}
                    >
                        <i
                            className={`fa far fa-file-word ${styles.itemIcon}`}
                            aria-hidden="true"
                        />
                        MS Word
                    </button>
                </div>
            ) : null}
        </div>
    )
}
