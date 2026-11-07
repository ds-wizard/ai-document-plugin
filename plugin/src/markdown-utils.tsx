import { Prose } from '@ds-wizard/plugin-sdk/ui/Prose'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownRendererProps = {
    markdown: string
}

/** Generated Markdown, typeset by the wizard's `Prose`; raw HTML in it is skipped. */
export function MarkdownRenderer({ markdown }: MarkdownRendererProps) {
    return (
        <Prose style={{ minWidth: 0, maxWidth: '100%' }}>
            <ReactMarkdown
                skipHtml
                remarkPlugins={[remarkGfm]}
                components={{
                    a: ({ node: _node, ...props }) => (
                        <a {...props} target="_blank" rel="noreferrer" />
                    ),
                    // Wide tables scroll on their own rather than widening the page.
                    table: ({ node: _node, ...props }) => (
                        <div style={{ maxWidth: '100%', overflowX: 'auto' }}>
                            <table {...props} />
                        </div>
                    ),
                }}
            >
                {markdown}
            </ReactMarkdown>
        </Prose>
    )
}
