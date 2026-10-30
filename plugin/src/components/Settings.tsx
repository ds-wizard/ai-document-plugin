import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { Toaster } from 'sonner'

import styles from '@/components/Settings.module.css'
import { LlmSettingsSection } from '@/components/settings/LlmSettingsSection'
import { TenantTemplateSection } from '@/components/settings/TenantTemplateSettings'
import { SettingsData } from '@/data/settings-data'

export default function Settings(_props: SettingsComponentProps<SettingsData>) {
    return (
        <div className={styles.root}>
            <Toaster richColors closeButton />
            <LlmSettingsSection />

            <TenantTemplateSection />
        </div>
    )
}
