import { SettingsComponentProps } from '@ds-wizard/plugin-sdk/elements'
import { Stack } from '@ds-wizard/plugin-sdk/ui/Layout'
import { Separator } from '@ds-wizard/plugin-sdk/ui/Separator'
import { Toaster } from 'sonner'

import { LlmSettingsSection } from '@/components/settings/LlmSettingsSection'
import { TenantTemplateSection } from '@/components/settings/TenantTemplateSettings'
import { SettingsData } from '@/data/settings-data'

export default function Settings(_props: SettingsComponentProps<SettingsData>) {
    return (
        <Stack loose style={{ maxWidth: '48rem' }}>
            <LlmSettingsSection />
            <Separator />
            <TenantTemplateSection />
            {/* Last, so its (empty) region does not push the content down. */}
            <Toaster richColors closeButton />
        </Stack>
    )
}
