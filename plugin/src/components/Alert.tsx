import type { ReactNode } from 'react'

import styles from '@/components/Alert.module.css'

export type AlertVariant = 'error' | 'success' | 'warning' | 'info'

type AlertProps = {
    variant: AlertVariant
    children?: ReactNode
}

export function Alert({ variant, children }: AlertProps) {
    if (!children) {
        return null
    }

    return (
        <div className={`${styles.alert} ${styles[variant]}`} role="alert">
            {children}
        </div>
    )
}
