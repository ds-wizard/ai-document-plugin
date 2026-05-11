import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownRendererProps = {
    markdown: string
}

export function MarkdownRenderer({ markdown }: MarkdownRendererProps) {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                a: ({ node: _node, ...props }) => (
                    <a {...props} target="_blank" rel="noreferrer" style={{ color: '#1d4ed8' }} />
                ),
                blockquote: ({ node: _node, ...props }) => (
                    <blockquote
                        {...props}
                        style={{
                            margin: 0,
                            padding: '0.25rem 0 0.25rem 1rem',
                            borderLeft: '4px solid #cbd5e1',
                            color: '#334155',
                        }}
                    />
                ),
                code: ({ node: _node, className, children, ...props }) => {
                    const isBlock = Boolean(className)

                    if (isBlock) {
                        return (
                            <code
                                {...props}
                                className={className}
                                style={{
                                    display: 'block',
                                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                                    background: '#0f172a',
                                    color: '#e2e8f0',
                                    borderRadius: '0.75rem',
                                    padding: '1rem',
                                    overflowX: 'auto',
                                    whiteSpace: 'pre',
                                }}
                            >
                                {children}
                            </code>
                        )
                    }

                    return (
                        <code
                            {...props}
                            className={className}
                            style={{
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                                background: '#e2e8f0',
                                borderRadius: '0.25rem',
                                padding: '0.1rem 0.3rem',
                            }}
                        >
                            {children}
                        </code>
                    )
                },
                h1: ({ node: _node, ...props }) => (
                    <h1
                        {...props}
                        style={{ fontSize: '2rem', fontWeight: 700, lineHeight: 1.2, margin: 0 }}
                    />
                ),
                h2: ({ node: _node, ...props }) => (
                    <h2
                        {...props}
                        style={{
                            fontSize: '1.65rem',
                            fontWeight: 700,
                            lineHeight: 1.2,
                            margin: 0,
                        }}
                    />
                ),
                h3: ({ node: _node, ...props }) => (
                    <h3
                        {...props}
                        style={{
                            fontSize: '1.35rem',
                            fontWeight: 700,
                            lineHeight: 1.2,
                            margin: 0,
                        }}
                    />
                ),
                h4: ({ node: _node, ...props }) => (
                    <h4
                        {...props}
                        style={{
                            fontSize: '1.15rem',
                            fontWeight: 700,
                            lineHeight: 1.2,
                            margin: 0,
                        }}
                    />
                ),
                h5: ({ node: _node, ...props }) => (
                    <h5
                        {...props}
                        style={{ fontSize: '1rem', fontWeight: 700, lineHeight: 1.2, margin: 0 }}
                    />
                ),
                h6: ({ node: _node, ...props }) => (
                    <h6
                        {...props}
                        style={{
                            fontSize: '0.95rem',
                            fontWeight: 700,
                            lineHeight: 1.2,
                            margin: 0,
                        }}
                    />
                ),
                hr: ({ node: _node, ...props }) => (
                    <hr
                        {...props}
                        style={{ width: '100%', border: 0, borderTop: '1px solid #cbd5e1' }}
                    />
                ),
                ol: ({ node: _node, ...props }) => (
                    <ol {...props} style={{ margin: 0, paddingLeft: '1.5rem' }} />
                ),
                p: ({ node: _node, ...props }) => (
                    <p {...props} style={{ margin: 0, color: '#1e293b', lineHeight: 1.7 }} />
                ),
                pre: ({ node: _node, ...props }) => <pre {...props} style={{ margin: 0 }} />,
                table: ({ node: _node, ...props }) => (
                    <div
                        style={{
                            overflowX: 'auto',
                            border: '1px solid #cbd5e1',
                            borderRadius: '0.75rem',
                            background: '#fff',
                        }}
                    >
                        <table
                            {...props}
                            style={{
                                width: '100%',
                                borderCollapse: 'collapse',
                                minWidth: '24rem',
                            }}
                        />
                    </div>
                ),
                td: ({ node: _node, ...props }) => (
                    <td
                        {...props}
                        style={{
                            padding: '0.75rem 0.9rem',
                            borderTop: '1px solid #e2e8f0',
                            color: '#1e293b',
                            verticalAlign: 'top',
                        }}
                    />
                ),
                th: ({ node: _node, ...props }) => (
                    <th
                        {...props}
                        style={{
                            textAlign: 'left',
                            padding: '0.75rem 0.9rem',
                            borderBottom: '1px solid #cbd5e1',
                            color: '#0f172a',
                        }}
                    />
                ),
                thead: ({ node: _node, ...props }) => (
                    <thead {...props} style={{ background: '#e2e8f0' }} />
                ),
                ul: ({ node: _node, ...props }) => (
                    <ul {...props} style={{ margin: 0, paddingLeft: '1.5rem' }} />
                ),
            }}
        >
            {markdown}
        </ReactMarkdown>
    )
}
