import type { ReactNode } from 'react'

import styles from '@/components/FeedbackAlert.module.css'

export type AlertKind = 'error' | 'info' | 'success' | 'warning'

type FeedbackAlertProps = {
    kind: AlertKind
    children: ReactNode
}

export function FeedbackAlert({ kind, children }: FeedbackAlertProps) {
    if (!children) {
        return null
    }

    return <div className={`${styles.alert} ${styles[kind]}`}>{children}</div>
}
