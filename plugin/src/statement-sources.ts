/** Remove source metadata for downloads while preserving the enclosed Markdown. */
export function stripStatementSources(markdown: string): string {
    return markdown.replace(
        /<statement\s+source\s*=\s*(?:"[^"]*"|'[^']*')\s*>|<\/statement\s*>/g,
        '',
    )
}

/** Render statement metadata as links without enabling arbitrary HTML in Markdown. */
export function prepareStatementSources(markdown: string, projectUuid: string, dswUrl: string) {
    const sourceLinks = new Map<string, string>()
    const projectUrl = new URL(`/wizard/projects/${encodeURIComponent(projectUuid)}`, dswUrl)
    // Leave fenced code and inline code untouched. Statements may span multiple lines.
    // Adjacent statement elements form flowing prose, even when separated by blank lines.
    const tokens =
        /(^ {0,3}(`{3,}|~{3,})[^\n]*\n[\s\S]*?^ {0,3}\2[^\S\n]*(?:\n|$))|(`+)[^`]*?\3|<statement\s+source\s*=\s*(?:"([^"]*)"|'([^']*)')\s*>([\s\S]*?)<\/statement\s*>(\s*(?=<statement\s+source\s*=))?/gm
    const renderedMarkdown = markdown.replace(
        tokens,
        (
            match,
            fence,
            _fenceMarker,
            code,
            doubleSource,
            singleSource,
            content,
            separator,
            offset,
        ) => {
            if (fence || code) return match
            const paths = [...new Set<string>((doubleSource ?? singleSource).trim().split(/\s+/))]
            const links = paths.filter(Boolean).map((path) => {
                const url = new URL(projectUrl)
                url.searchParams.set('questionPath', path)
                const href = url.href
                sourceLinks.set(href, path)
                return `[↗](<${href}>)`
            })
            const hasNextStatement =
                separator !== undefined || markdown.startsWith('<statement ', offset + match.length)
            return `${content.trim()}${links.length ? ` ${links.join(' ')}` : ''}${hasNextStatement ? ' ' : ''}`
        },
    )
    return { markdown: renderedMarkdown, sourceLinks }
}
