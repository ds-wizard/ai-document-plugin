import { Fragment, ReactNode } from 'react'

export const formatInlineMarkdown = (text: string): ReactNode[] => {
    const pattern = /(\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*)/g
    const parts: ReactNode[] = []
    let lastIndex = 0

    for (const match of text.matchAll(pattern)) {
        const fullMatch = match[0]
        const index = match.index ?? 0

        if (index > lastIndex) {
            parts.push(text.slice(lastIndex, index))
        }

        if (match[2] && match[3]) {
            parts.push(
                <a
                    key={`${index}-${fullMatch}`}
                    href={match[3]}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#1d4ed8' }}
                >
                    {match[2]}
                </a>,
            )
        } else if (match[4]) {
            parts.push(
                <code
                    key={`${index}-${fullMatch}`}
                    style={{
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        background: '#e2e8f0',
                        borderRadius: '0.25rem',
                        padding: '0.1rem 0.3rem',
                    }}
                >
                    {match[4]}
                </code>,
            )
        } else if (match[5]) {
            parts.push(<strong key={`${index}-${fullMatch}`}>{match[5]}</strong>)
        } else if (match[6]) {
            parts.push(<em key={`${index}-${fullMatch}`}>{match[6]}</em>)
        }

        lastIndex = index + fullMatch.length
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex))
    }

    return parts.length > 0 ? parts : [text]
}

export const renderMarkdownBlocks = (markdown: string): ReactNode[] => {
    const lines = markdown.replace(/\r\n/g, '\n').split('\n')
    const blocks: ReactNode[] = []
    let index = 0

    const isTableSeparatorLine = (value: string): boolean => {
        const cells = value
            .trim()
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((cell) => cell.trim())

        return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
    }

    const parseTableRow = (value: string): string[] =>
        value
            .trim()
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((cell) => cell.trim())

    while (index < lines.length) {
        const line = lines[index]
        const trimmed = line.trim()

        if (!trimmed) {
            index += 1
            continue
        }

        if (trimmed.startsWith('```')) {
            const codeLines: string[] = []
            index += 1

            while (index < lines.length && !lines[index].trim().startsWith('```')) {
                codeLines.push(lines[index])
                index += 1
            }

            if (index < lines.length) {
                index += 1
            }

            blocks.push(
                <pre
                    key={`code-${blocks.length}`}
                    style={{
                        margin: 0,
                        padding: '1rem',
                        borderRadius: '0.75rem',
                        background: '#0f172a',
                        color: '#e2e8f0',
                        overflowX: 'auto',
                    }}
                >
                    <code>{codeLines.join('\n')}</code>
                </pre>,
            )
            continue
        }

        if (/^#{1,6}\s+/.test(trimmed)) {
            const level = Math.min(trimmed.match(/^#+/)?.[0].length ?? 1, 6)
            const content = trimmed.replace(/^#{1,6}\s+/, '')
            const fontSizes = ['2rem', '1.65rem', '1.35rem', '1.15rem', '1rem', '0.95rem']
            blocks.push(
                <div
                    key={`heading-${blocks.length}`}
                    style={{
                        fontSize: fontSizes[level - 1],
                        fontWeight: 700,
                        lineHeight: 1.2,
                        marginTop: blocks.length === 0 ? 0 : '0.5rem',
                    }}
                >
                    {formatInlineMarkdown(content)}
                </div>,
            )
            index += 1
            continue
        }

        if (/^(-|\*)\s+/.test(trimmed)) {
            const items: string[] = []

            while (index < lines.length && /^(-|\*)\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^(-|\*)\s+/, ''))
                index += 1
            }

            blocks.push(
                <ul key={`ul-${blocks.length}`} style={{ margin: 0, paddingLeft: '1.5rem' }}>
                    {items.map((item, itemIndex) => (
                        <li key={`${itemIndex}-${item}`}>{formatInlineMarkdown(item)}</li>
                    ))}
                </ul>,
            )
            continue
        }

        if (/^\d+\.\s+/.test(trimmed)) {
            const items: string[] = []

            while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^\d+\.\s+/, ''))
                index += 1
            }

            blocks.push(
                <ol key={`ol-${blocks.length}`} style={{ margin: 0, paddingLeft: '1.5rem' }}>
                    {items.map((item, itemIndex) => (
                        <li key={`${itemIndex}-${item}`}>{formatInlineMarkdown(item)}</li>
                    ))}
                </ol>,
            )
            continue
        }

        if (trimmed.startsWith('>')) {
            const quoteLines: string[] = []

            while (index < lines.length && lines[index].trim().startsWith('>')) {
                quoteLines.push(lines[index].trim().replace(/^>\s?/, ''))
                index += 1
            }

            blocks.push(
                <blockquote
                    key={`quote-${blocks.length}`}
                    style={{
                        margin: 0,
                        padding: '0.25rem 0 0.25rem 1rem',
                        borderLeft: '4px solid #cbd5e1',
                        color: '#334155',
                    }}
                >
                    {quoteLines.map((quoteLine, quoteIndex) => (
                        <Fragment key={`${quoteIndex}-${quoteLine}`}>
                            {quoteIndex > 0 ? <br /> : null}
                            {formatInlineMarkdown(quoteLine)}
                        </Fragment>
                    ))}
                </blockquote>,
            )
            continue
        }

        if (/^---+$/.test(trimmed)) {
            blocks.push(
                <hr
                    key={`hr-${blocks.length}`}
                    style={{ width: '100%', border: 0, borderTop: '1px solid #cbd5e1' }}
                />,
            )
            index += 1
            continue
        }

        if (
            index + 1 < lines.length &&
            trimmed.includes('|') &&
            isTableSeparatorLine(lines[index + 1])
        ) {
            const headerCells = parseTableRow(trimmed)
            const bodyRows: string[][] = []
            index += 2

            while (index < lines.length) {
                const rowLine = lines[index].trim()
                if (!rowLine || !rowLine.includes('|')) {
                    break
                }

                bodyRows.push(parseTableRow(rowLine))
                index += 1
            }

            blocks.push(
                <div
                    key={`table-${blocks.length}`}
                    style={{
                        overflowX: 'auto',
                        border: '1px solid #cbd5e1',
                        borderRadius: '0.75rem',
                        background: '#fff',
                    }}
                >
                    <table
                        style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            minWidth: '24rem',
                        }}
                    >
                        <thead style={{ background: '#e2e8f0' }}>
                            <tr>
                                {headerCells.map((cell, cellIndex) => (
                                    <th
                                        key={`${cellIndex}-${cell}`}
                                        style={{
                                            textAlign: 'left',
                                            padding: '0.75rem 0.9rem',
                                            borderBottom: '1px solid #cbd5e1',
                                            color: '#0f172a',
                                        }}
                                    >
                                        {formatInlineMarkdown(cell)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {bodyRows.map((row, rowIndex) => (
                                <tr key={`${rowIndex}-${row.join('|')}`}>
                                    {headerCells.map((_, cellIndex) => (
                                        <td
                                            key={`${rowIndex}-${cellIndex}`}
                                            style={{
                                                padding: '0.75rem 0.9rem',
                                                borderTop:
                                                    rowIndex === 0 ? 'none' : '1px solid #e2e8f0',
                                                color: '#1e293b',
                                                verticalAlign: 'top',
                                            }}
                                        >
                                            {formatInlineMarkdown(row[cellIndex] || '')}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>,
            )
            continue
        }

        const paragraphLines: string[] = []
        while (index < lines.length && lines[index].trim()) {
            const candidate = lines[index].trim()
            if (
                candidate.startsWith('```') ||
                /^#{1,6}\s+/.test(candidate) ||
                /^(-|\*)\s+/.test(candidate) ||
                /^\d+\.\s+/.test(candidate) ||
                candidate.startsWith('>') ||
                (index + 1 < lines.length &&
                    candidate.includes('|') &&
                    isTableSeparatorLine(lines[index + 1])) ||
                /^---+$/.test(candidate)
            ) {
                break
            }

            paragraphLines.push(candidate)
            index += 1
        }

        if (paragraphLines.length > 0) {
            blocks.push(
                <p
                    key={`p-${blocks.length}`}
                    style={{ margin: 0, color: '#1e293b', lineHeight: 1.7 }}
                >
                    {formatInlineMarkdown(paragraphLines.join(' '))}
                </p>,
            )
            continue
        }

        index += 1
    }

    return blocks
}
