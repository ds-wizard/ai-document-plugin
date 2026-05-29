const COOKIE_PREFIX = 'ai-dmp-export-last-run'

const buildCookieName = (projectUuid: string): string => `${COOKIE_PREFIX}-${projectUuid}`

export const getLastExportRunId = (projectUuid: string): string | null => {
    const cookieName = `${buildCookieName(projectUuid)}=`
    const match = document.cookie
        .split(';')
        .map((entry) => entry.trim())
        .find((entry) => entry.startsWith(cookieName))

    if (!match) {
        return null
    }

    const runId = decodeURIComponent(match.slice(cookieName.length))
    return runId || null
}

export const setLastExportRunId = (projectUuid: string, runId: string): void => {
    const cookieName = buildCookieName(projectUuid)
    const maxAgeSeconds = 60 * 60 * 24 * 30
    document.cookie = `${cookieName}=${encodeURIComponent(runId)}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`
}
