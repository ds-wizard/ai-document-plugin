import { toast } from 'sonner'

import { exportTemplateAsJson } from '@/client'
import type { TemplateOption } from '@/types'

export const triggerBlobDownload = (blob: Blob, fileName: string) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
}

/** Downloads the template as a JSON file and reports the outcome with a toast. */
export const downloadTemplateJson = async ({
    uuid,
    title,
}: Pick<TemplateOption, 'uuid' | 'title'>) => {
    try {
        const blob = await exportTemplateAsJson(uuid)
        triggerBlobDownload(blob, `${title}.json`)
        toast.success('Template JSON download has started.')
    } catch (error) {
        toast.error(
            error instanceof Error ? error.message : 'Failed to export the template as JSON.',
        )
    }
}
