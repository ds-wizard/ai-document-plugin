import { useEffect, useState } from 'react'

import { getCoverPagePreview } from '@/client'
import styles from '@/components/CoverPagePreview.module.css'
import { getLanguageOption } from '@/data/languages'
import type { CoverPagePreviewDefinition } from '@/types'

type CoverPagePreviewProps = {
    language: string
}

export function CoverPagePreview({ language }: CoverPagePreviewProps) {
    const languageName = getLanguageOption(language)?.englishLabel ?? language
    const [definition, setDefinition] = useState<CoverPagePreviewDefinition | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false

        void getCoverPagePreview()
            .then((loadedDefinition) => {
                if (!cancelled) {
                    setDefinition(loadedDefinition)
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setError('The cover page preview could not be loaded.')
                }
            })

        return () => {
            cancelled = true
        }
    }, [])

    return (
        <details className={styles.root}>
            <summary className={styles.summary}>Preview the cover page</summary>
            <div className={styles.content}>
                {error && <p className={styles.note}>{error}</p>}
                {!error && !definition && <p className={styles.note}>Loading preview...</p>}
                {definition && (
                    <>
                        {language.toLowerCase().split('-')[0] !== 'en' && (
                            <p className={styles.note}>
                                Labels are shown here in English and will be translated into{' '}
                                {languageName} during generation.
                            </p>
                        )}

                        <section aria-label="Cover page structure" className={styles.page}>
                            <h3 className={styles.title}>{definition.metadata.title.text}</h3>
                            <div className={styles.tableWrapper}>
                                <table className={styles.table}>
                                    <thead>
                                        <tr>
                                            {definition.metadata.columns.map((column) => (
                                                <th key={column.id} scope="col">
                                                    {column.text}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {definition.metadata.fields.map((field) => (
                                            <tr key={field.id}>
                                                <th scope="row">{field.label}</th>
                                                <td className={styles.placeholder}>
                                                    {field.preview}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <p className={styles.attribution}>{definition.metadata.attribution}</p>

                            <h4 className={styles.heading}>{definition.history.title.text}</h4>
                            <div className={styles.tableWrapper}>
                                <table className={styles.table}>
                                    <thead>
                                        <tr>
                                            {definition.history.columns.map((column) => (
                                                <th key={column.id} scope="col">
                                                    {column.text}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td
                                                colSpan={definition.history.columns.length}
                                                className={styles.placeholder}
                                            >
                                                {definition.history.preview}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>

                            {definition.assignedSections.map((section) => (
                                <div key={section.id}>
                                    <h3 className={styles.heading}>{section.title}</h3>
                                    <p className={styles.note}>{section.preview}</p>
                                    <ul className={styles.fields}>
                                        {section.fields.map((field) => (
                                            <li key={field.id}>{field.label}</li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </section>
                    </>
                )}
            </div>
        </details>
    )
}
