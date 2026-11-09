import { Prose } from '@ds-wizard/plugin-sdk/ui/Prose'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import styles from '@/MarkdownRenderer.module.css'
import { prepareStatementSources } from '@/statement-sources'

type MarkdownRendererProps = {
    markdown: string
    projectUuid: string
}

export function MarkdownRenderer({ markdown, projectUuid }: MarkdownRendererProps) {
    const prepared = prepareStatementSources(markdown, projectUuid, window.location.origin)
    return (
        <Prose style={{ minWidth: 0, maxWidth: '100%' }}>
            <ReactMarkdown
                skipHtml
                remarkPlugins={[remarkGfm]}
                components={{
                    a: ({ node: _node, href, children, ...props }) => {
                        const source = href ? prepared.sourceLinks.get(href) : undefined
                        return (
                            <a
                                {...props}
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={source ? styles.sourceLink : undefined}
                                title={source ? `Open source question: ${source}` : props.title}
                                aria-label={
                                    source ? `Open source question: ${source} (new tab)` : undefined
                                }
                            >
                                {source ? (
                                    <i className="fas fa-external-link-alt" aria-hidden="true" />
                                ) : (
                                    children
                                )}
                            </a>
                        )
                    },
                    // Wide tables scroll on their own rather than widening the page.
                    table: ({ node: _node, ...props }) => (
                        <div style={{ maxWidth: '100%', overflowX: 'auto' }}>
                            <table {...props} />
                        </div>
                    ),
                }}
            >
                {prepared.markdown}
            </ReactMarkdown>
        </Prose>
    )
}
