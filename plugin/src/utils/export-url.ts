export const AI_EXPORT_ID_QUERY_PARAM = 'aiExportId'

export const getAiExportIdFromUrl = (): string | null => {
    return new URLSearchParams(window.location.search).get(AI_EXPORT_ID_QUERY_PARAM)
}

export const pushAiExportIdToUrl = (runId: string): void => {
    const url = new URL(window.location.href)
    url.searchParams.set(AI_EXPORT_ID_QUERY_PARAM, runId)
    window.history.pushState(null, '', url)
}

export const navigateBackFromExport = (): void => {
    window.history.back()
}
