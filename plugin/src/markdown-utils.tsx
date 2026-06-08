import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import styles from '@/MarkdownRenderer.module.css'

type MarkdownRendererProps = {
    markdown: string
}

export function MarkdownRenderer({ markdown }: MarkdownRendererProps) {
    return (
        <div className={styles.root}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    a: ({ node: _node, ...props }) => (
                        <a {...props} target="_blank" rel="noreferrer" />
                    ),
                    blockquote: ({ node: _node, ...props }) => <blockquote {...props} />,
                    code: ({ node: _node, className, children, ...props }) => {
                        const isBlock = Boolean(className)

                        return (
                            <code
                                {...props}
                                className={isBlock ? styles.codeBlock : styles.codeInline}
                            >
                                {children}
                            </code>
                        )
                    },
                    h1: ({ node: _node, ...props }) => <h1 {...props} />,
                    h2: ({ node: _node, ...props }) => <h2 {...props} />,
                    h3: ({ node: _node, ...props }) => <h3 {...props} />,
                    h4: ({ node: _node, ...props }) => <h4 {...props} />,
                    h5: ({ node: _node, ...props }) => <h5 {...props} />,
                    h6: ({ node: _node, ...props }) => <h6 {...props} />,
                    hr: ({ node: _node, ...props }) => <hr {...props} />,
                    ol: ({ node: _node, ...props }) => <ol {...props} />,
                    p: ({ node: _node, ...props }) => <p {...props} />,
                    pre: ({ node: _node, ...props }) => <pre {...props} />,
                    table: ({ node: _node, ...props }) => (
                        <div className={styles.tableWrapper}>
                            <table {...props} />
                        </div>
                    ),
                    td: ({ node: _node, ...props }) => <td {...props} />,
                    th: ({ node: _node, ...props }) => <th {...props} />,
                    thead: ({ node: _node, ...props }) => <thead {...props} />,
                    ul: ({ node: _node, ...props }) => <ul {...props} />,
                }}
            >
                {markdown}
            </ReactMarkdown>
        </div>
    )
}
