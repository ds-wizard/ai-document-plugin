import styles from '@/components/DocumentHeaderPreview.module.css'
import { getLanguageOption } from '@/data/languages'

type DocumentHeaderPreviewProps = {
    language: string
}

const METADATA_FIELDS = [
    ['Project Name', 'Your project name'],
    ['Based On', 'Knowledge model name and version'],
    ['Project Phase', 'Current project phase'],
    ['Created By', 'Author'],
    ['Generated On', 'Date of generation'],
]

const PROJECT_FIELDS = [
    'Project title',
    'Project acronym',
    'Project number/code',
    'Funding',
    'Project duration',
    'Project abstract',
]

export function DocumentHeaderPreview({ language }: DocumentHeaderPreviewProps) {
    const languageName = getLanguageOption(language)?.englishLabel ?? language

    return (
        <details className={styles.root}>
            <summary className={styles.summary}>Preview these introductory pages</summary>
            <div className={styles.content}>
                <p className={styles.note}>
                    {language.toLowerCase().split('-')[0] !== 'en' &&
                        ` Labels are shown here in English and will be translated into ${languageName} during generation.`}
                </p>

                <section aria-label="Document header structure" className={styles.page}>
                    <h3 className={styles.title}>Data Management Plan</h3>
                    <div className={styles.tableWrapper}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th scope="col">Field</th>
                                    <th scope="col">Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                {METADATA_FIELDS.map(([label, source]) => (
                                    <tr key={label}>
                                        <th scope="row">{label}</th>
                                        <td className={styles.placeholder}>{source}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className={styles.attribution}>
                        Data Management Plan created in Data Stewardship Wizard «ds-wizard.org»
                        using AI document generation plugin
                    </p>

                    <h4 className={styles.heading}>History of Changes</h4>
                    <div className={styles.tableWrapper}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th scope="col">Version</th>
                                    <th scope="col">Date</th>
                                    <th scope="col">Changes</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colSpan={3} className={styles.placeholder}>
                                        Named project versions and their descriptions, newest first. Empty
                                        if no versions are available.
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <h3 className={styles.heading}>Projects</h3>
                    <p className={styles.note}>
                        A subsection for each project, using its original title. Details come from
                        questionnaire answers; unanswered optional fields are omitted.
                    </p>
                    <ul className={styles.fields}>
                        {PROJECT_FIELDS.map((label) => (
                            <li key={label}>{label}</li>
                        ))}
                    </ul>
                </section>
            </div>
        </details>
    )
}
